"""Demo tooling: make something actually happen, so the live update is real.

A dashboard that updates because a timer fired is a screensaver. These endpoints
write real rows - a new participant, a new adverse event, a new protocol deviation
- record who did it in the audit trail, and then publish an event so every open
dashboard recomputes. The enrolment count moves from 186 to 187 because there is a
187th person in the table, and `scripts/seed.py --reset` puts it back.

Two things are deliberately *not* relaxed here:

  Permissions still apply. A Sponsor cannot enrol anybody, because in a real trial
  a monitor who could edit the data would undermine the data. The demo for that is
  better anyway: open the Sponsor's screen, have the site coordinator enrol someone
  in another tab, and watch the Sponsor's total move on its own.

  Site scoping still applies. A site-scoped user's simulated enrolment lands at
  their own site and nowhere else.

The rows use the same free-text style as the seeded ones, on purpose: Phase 4's
NLP reads `description`, and it should have nothing to distinguish a simulated
event from a seeded one.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app import audit, synthetic
from app.db import get_session
from app.enums import (
    AuditAction,
    Prakriti,
    Sex,
    StudyArm,
    SubjectStatus,
    VisitStatus,
)
from app.events import bus, now_iso
from app.models import AdverseEvent, Site, Subject, Trial, Visit
from app.rbac import CurrentUser, Permission, get_current_user, require
from app.routers.stats import resolve_trial

router = APIRouter(prefix="/api/simulate", tags=["simulate"])

# Each simulated action, what it needs, and what it moves on screen. Served by
# `/api/simulate/options` so the UI can label its buttons and explain a greyed-out
# one instead of just failing.
ACTIONS = [
    {
        "key": "enrollment",
        "path": "/api/simulate/enrollment",
        "label": "Enrol a participant",
        "permission": Permission.SUBJECT_WRITE.value,
        "moves": "Screened, Enrolled, % of target, the recruitment curve",
    },
    {
        "key": "adverse-event",
        "path": "/api/simulate/adverse-event",
        "label": "Report an adverse event",
        "permission": Permission.AE_WRITE.value,
        "moves": "Adverse events, Serious events, Events awaiting coding",
    },
    {
        "key": "deviation",
        "path": "/api/simulate/deviation",
        "label": "Log a protocol deviation",
        "permission": Permission.VISIT_WRITE.value,
        "moves": "Protocol deviations, Deviation rate, Visits completed",
    },
]


class SimulateRequest(BaseModel):
    """Optional knobs. Every field has a sensible default, so `{}` works."""

    site_id: int | None = Field(
        None, description="which site (ignored for site-scoped users: always their own)"
    )
    trial_id: int | None = None
    serious: bool = Field(
        False, description="adverse events only: report a serious (reportable) event"
    )


# --------------------------------------------------------------------- helpers


def _trial(session: Session, trial_id: int | None) -> Trial:
    trial = resolve_trial(session, trial_id)
    if trial is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "there is no trial to simulate against. Load the synthetic dataset "
                "first: docker compose exec backend python scripts/seed.py"
            ),
        )
    return trial


def _site(session: Session, trial: Trial, user: CurrentUser, requested: int | None) -> Site:
    """Which site this simulated action belongs to.

    A site-scoped user gets their own site and cannot ask for another - the
    request body is not a way around the scope any more than the query string is.
    """
    scope = user.scope_site_id
    if scope is not None:
        site = session.get(Site, scope)
        if site is None:
            raise HTTPException(
                status_code=409,
                detail="your account is attached to a site that no longer exists",
            )
        return site

    if requested is not None:
        site = session.get(Site, requested)
        if site is None or site.trial_id != trial.id:
            raise HTTPException(
                status_code=404, detail=f"no site with id {requested} in this trial"
            )
        return site

    site = session.exec(
        select(Site).where(Site.trial_id == trial.id).order_by(Site.site_code)
    ).first()
    if site is None:
        raise HTTPException(status_code=409, detail="this trial has no sites")
    return site


def _next_subject_code(session: Session, site: Site) -> str:
    """Continue the site's existing numbering: AIIA-ASH-01-057 after ...-056."""
    prefix = f"AIIA-ASH-{site.site_code}-"
    codes = session.exec(
        select(Subject.subject_code).where(Subject.site_id == site.id)
    ).all()
    highest = 0
    for code in codes:
        tail = code.rsplit("-", 1)[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{prefix}{highest + 1:03d}"


def _next_ae_number(session: Session, trial: Trial) -> str:
    numbers = session.exec(
        select(AdverseEvent.ae_number).where(AdverseEvent.trial_id == trial.id)
    ).all()
    highest = 0
    for number in numbers:
        tail = number.rsplit("-", 1)[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"AE-{highest + 1:04d}"


def _balanced_arm(session: Session, trial: Trial) -> str:
    """Put the new participant in whichever arm is currently smaller.

    Real randomisation is not this, obviously. But a demo that unbalances the arms
    every time somebody presses the button would make the sponsor's balance chart
    say something untrue about the study design.
    """
    counts = dict(
        session.exec(
            select(Subject.arm, func.count())
            .where(Subject.trial_id == trial.id, Subject.arm.is_not(None))  # type: ignore[union-attr]
            .group_by(Subject.arm)
        ).all()
    )
    arms = [StudyArm.TREATMENT.value, StudyArm.PLACEBO.value]
    return min(arms, key=lambda arm: counts.get(arm, 0))


def _random_enrolled_subject(session: Session, site: Site) -> Subject:
    subjects = session.exec(
        select(Subject).where(
            Subject.site_id == site.id,
            Subject.enrollment_date.is_not(None),  # type: ignore[union-attr]
        )
    ).all()
    if not subjects:
        raise HTTPException(
            status_code=409,
            detail=(
                f"nobody is enrolled at site {site.site_code} yet, so there is no "
                "participant to report an event for. Simulate an enrolment first."
            ),
        )
    return random.choice(list(subjects))


async def _publish(
    *,
    kind: str,
    message: str,
    trial: Trial,
    site: Site,
    label: str,
    entity_id: int | None,
    user: CurrentUser,
) -> dict:
    """Announce the change to every open dashboard."""
    return await bus.publish(
        {
            "type": kind,
            "at": now_iso(),
            "trial_id": trial.id,
            # The WebSocket uses this to decide whether a site-scoped viewer should
            # be told about the event at all.
            "site_id": site.id,
            "site_code": site.site_code,
            "label": label,
            "entity_id": entity_id,
            "message": message,
            "actor": {
                "email": user.email,
                "name": user.full_name,
                "role": user.role,
                "role_label": user.role_label,
            },
        }
    )


# ------------------------------------------------------------------- endpoints


@router.get("/options")
def options(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Which simulated actions this user may fire, and why not if they cannot.

    Lets the UI grey out a button with an honest explanation rather than letting
    someone click it into a 403.
    """
    return {
        "role": user.role,
        "role_label": user.role_label,
        "site_scoped": user.is_site_scoped,
        "site_id": user.site_id,
        "actions": [
            {
                **action,
                "allowed": user.can(Permission(action["permission"])),
                "why_not": (
                    None
                    if user.can(Permission(action["permission"]))
                    else f"A {user.role_label} does not enter trial data. Log in as the "
                    "Principal Investigator or Coordinator to do this - this screen "
                    "will update on its own when they do."
                ),
            }
            for action in ACTIONS
        ],
        "note": (
            "These write real rows and real audit entries. Restore the baseline "
            "dataset with: docker compose exec backend python scripts/seed.py --reset"
        ),
    }


@router.post("/enrollment", status_code=201)
async def simulate_enrollment(
    request: Request,
    body: SimulateRequest | None = None,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> dict:
    """Screen and enrol one new participant at this user's site, today."""
    body = body or SimulateRequest()
    trial = _trial(session, body.trial_id)
    site = _site(session, trial, user, body.site_id)
    if site.trial_id != trial.id:
        raise HTTPException(
            status_code=404, detail=f"no site with id {site.id} in this trial"
        )

    today = date.today()
    rng = random.Random()
    code = _next_subject_code(session, site)
    age = rng.randint(22, 58)

    subject = Subject(
        trial_id=trial.id,
        site_id=site.id,
        subject_code=code,
        status=SubjectStatus.ENROLLED.value,
        # Screened a fortnight ago and enrolled today, which is the protocol's own
        # screening window rather than an arbitrary gap.
        screening_date=today - timedelta(days=14),
        enrollment_date=today,
        randomization_date=today,
        arm=_balanced_arm(session, trial),
        year_of_birth=today.year - age,
        age_at_enrollment=age,
        sex=rng.choice([Sex.MALE.value, Sex.FEMALE.value]),
        height_cm=round(rng.uniform(150, 180), 1),
        weight_kg=round(rng.uniform(48, 88), 1),
        # Prakriti is assessed once, at enrolment - so this is exactly when it is set.
        prakriti=rng.choice([p.value for p in Prakriti]),
    )
    session.add(subject)
    session.flush()  # assigns subject.id without ending the transaction

    # The protocol's whole visit schedule, so the new participant looks like every
    # other one rather than a bare row with no appointments.
    for number, (visit_name, day_offset) in enumerate(synthetic.VISIT_SCHEDULE, start=1):
        scheduled = today + timedelta(days=day_offset)
        session.add(
            Visit(
                subject_id=subject.id,
                trial_id=trial.id,
                visit_name=visit_name,
                visit_number=number,
                visit_day=day_offset,
                scheduled_date=scheduled,
                actual_date=scheduled if day_offset <= 0 else None,
                status=(
                    VisitStatus.COMPLETED.value
                    if day_offset <= 0
                    else VisitStatus.SCHEDULED.value
                ),
                performed_by_user_id=user.id if day_offset <= 0 else None,
            )
        )

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="subjects",
        entity_id=subject.id,
        entity_label=code,
        reason="simulated enrolment (live demo)",
        trial_id=trial.id,
        request=request,
    )
    session.commit()
    session.refresh(subject)

    event = await _publish(
        kind="subject.enrolled",
        message=f"{code} enrolled at {site.site_code} {site.name}",
        trial=trial,
        site=site,
        label=code,
        entity_id=subject.id,
        user=user,
    )
    return {
        "created": "subject",
        "subject": {
            "id": subject.id,
            "subject_code": subject.subject_code,
            "site_code": site.site_code,
            "arm": subject.arm,
            "prakriti": subject.prakriti,
            "enrollment_date": subject.enrollment_date,
        },
        "event": event,
        "audited": True,
    }


@router.post("/adverse-event", status_code=201)
async def simulate_adverse_event(
    request: Request,
    body: SimulateRequest | None = None,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_WRITE)),
) -> dict:
    """Report one adverse event for a participant at this user's site.

    Pass `{"serious": true}` for an event that meets a regulatory seriousness
    criterion - that is the one that moves the Ethics Committee and Regulator
    screens, because a serious event starts a reporting clock.
    """
    body = body or SimulateRequest()
    trial = _trial(session, body.trial_id)
    site = _site(session, trial, user, body.site_id)
    subject = _random_enrolled_subject(session, site)

    today = date.today()
    catalogue = synthetic.SAE_CATALOGUE if body.serious else synthetic.AE_CATALOGUE
    template = random.choice(catalogue)
    number = _next_ae_number(session, trial)

    event_row = AdverseEvent(
        subject_id=subject.id,
        trial_id=trial.id,
        site_id=site.id,
        ae_number=number,
        term_verbatim=template["term_verbatim"],
        description=template["description"],
        onset_date=today,
        # A serious event is by definition unresolved at the moment it is reported;
        # a mild one is usually written up after it settled.
        resolution_date=None if body.serious else today,
        severity=template["severity"],
        is_serious=bool(body.serious),
        seriousness_criteria=template.get("seriousness_criteria"),
        causality=template["causality"],
        outcome=template["outcome"],
        action_taken=template.get("action_taken"),
        reported_by_user_id=user.id,
        reported_date=today,
        # Reported to the ethics committee same day, which is what the rules want
        # and what makes this event show as "on time" on their screen.
        reported_to_ec=bool(body.serious),
        reported_to_ec_date=today if body.serious else None,
        # No MedDRA code: it lands in Phase 4's coding queue, like every other row.
        meddra_pt_code=None,
    )
    session.add(event_row)
    session.flush()

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="adverse_events",
        entity_id=event_row.id,
        entity_label=number,
        reason=(
            "simulated serious adverse event (live demo)"
            if body.serious
            else "simulated adverse event (live demo)"
        ),
        trial_id=trial.id,
        request=request,
    )
    session.commit()
    session.refresh(event_row)

    kind = "adverse_event.serious" if body.serious else "adverse_event.reported"
    published = await _publish(
        kind=kind,
        message=(
            f"{'Serious a' if body.serious else 'A'}dverse event {number} "
            f"({template['term_verbatim']}) reported for {subject.subject_code}"
        ),
        trial=trial,
        site=site,
        label=number,
        entity_id=event_row.id,
        user=user,
    )
    return {
        "created": "adverse_event",
        "adverse_event": {
            "id": event_row.id,
            "ae_number": number,
            "subject_code": subject.subject_code,
            "site_code": site.site_code,
            "term_verbatim": event_row.term_verbatim,
            "severity": event_row.severity,
            "is_serious": event_row.is_serious,
            "causality": event_row.causality,
            "onset_date": event_row.onset_date,
        },
        "event": published,
        "audited": True,
    }


@router.post("/deviation", status_code=201)
async def simulate_deviation(
    request: Request,
    body: SimulateRequest | None = None,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_WRITE)),
) -> dict:
    """Complete the next scheduled visit at this site, late, as a deviation.

    A deviation is anything that departs from the protocol - here, a visit done
    outside its window. Recording one is not an admission of failure; hiding one
    is the failure.
    """
    body = body or SimulateRequest()
    trial = _trial(session, body.trial_id)
    site = _site(session, trial, user, body.site_id)

    visit = session.exec(
        select(Visit)
        .where(
            Visit.trial_id == trial.id,
            Visit.status == VisitStatus.SCHEDULED.value,
            Visit.subject_id.in_(  # type: ignore[union-attr]
                select(Subject.id).where(Subject.site_id == site.id)
            ),
        )
        .order_by(Visit.scheduled_date)
    ).first()
    if visit is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"there are no scheduled visits left at site {site.site_code} to "
                "record a deviation against."
            ),
        )

    subject = session.get(Subject, visit.subject_id)
    late_by = random.randint(4, 11)
    actual = (visit.scheduled_date or date.today()) + timedelta(days=late_by)

    previous_status = visit.status
    visit.status = VisitStatus.COMPLETED.value
    visit.actual_date = actual
    visit.is_protocol_deviation = True
    visit.deviation_description = (
        f"Visit performed {late_by} days outside the protocol window. Subject was "
        "travelling and could not attend on the scheduled date; assessments "
        "completed in full at the later visit. Reported as a deviation."
    )
    visit.performed_by_user_id = user.id
    session.add(visit)

    audit.record(
        session,
        user=user,
        action=AuditAction.UPDATE,
        entity_type="visits",
        entity_id=visit.id,
        entity_label=f"{subject.subject_code if subject else '?'} {visit.visit_name}",
        field_name="status",
        old_value=previous_status,
        new_value=visit.status,
        reason=f"simulated protocol deviation: visit {late_by} days late (live demo)",
        trial_id=trial.id,
        request=request,
    )
    session.commit()
    session.refresh(visit)

    label = f"{subject.subject_code if subject else '?'} {visit.visit_name}"
    published = await _publish(
        kind="visit.deviation",
        message=f"Protocol deviation logged: {label}, {late_by} days late",
        trial=trial,
        site=site,
        label=label,
        entity_id=visit.id,
        user=user,
    )
    return {
        "created": "protocol_deviation",
        "visit": {
            "id": visit.id,
            "subject_code": subject.subject_code if subject else None,
            "site_code": site.site_code,
            "visit_name": visit.visit_name,
            "scheduled_date": visit.scheduled_date,
            "actual_date": visit.actual_date,
            "days_late": late_by,
            "deviation_description": visit.deviation_description,
        },
        "event": published,
        "audited": True,
    }
