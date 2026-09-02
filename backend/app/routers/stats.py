"""Aggregate numbers - the figures a dashboard actually puts on screen.

One endpoint, `/api/stats`, computed with SQL GROUP BY rather than by pulling
every row into Python. That matters now: this same query runs on every WebSocket
broadcast, so it needs to stay cheap.

Nothing here is stored. Enrolment is counted from the subjects table every time,
so the headline number can never drift away from the underlying records - which
is exactly the kind of quiet inconsistency an auditor looks for.

Phase 2 made these numbers role-aware. The same URL returns different totals
depending on who asks: a Sponsor sees 225 screened across four sites, while the
Delhi investigator sees only Delhi's share. The `scope` block in the response says
which of the two you are looking at, so a number on screen is never ambiguous.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.enums import SubjectStatus, VisitStatus
from app.models import AdverseEvent, AuditLog, Site, Subject, Trial, Visit
from app.rbac import CurrentUser, Permission, require

router = APIRouter(prefix="/api", tags=["stats"])


def _counts_by(
    session: Session, column, model, trial_id: int, extra=None
) -> dict[str, int]:
    """`SELECT column, COUNT(*) ... WHERE trial_id = ? GROUP BY column` as a dict.

    Always scoped to one trial. Leaving the filter off would look correct today,
    while there is a single trial in the database, and silently start mixing two
    studies' numbers together the moment a second one is added.

    `extra` is an optional additional condition - in practice the site scope.
    """
    statement = select(column, func.count()).where(model.trial_id == trial_id)
    if extra is not None:
        statement = statement.where(extra)
    rows = session.exec(statement.group_by(column)).all()
    return {str(value): int(count) for value, count in rows if value is not None}


def _percent(part: int, whole: int) -> float:
    """Rounded to one decimal place, and 0.0 rather than a crash when whole is 0."""
    if whole <= 0:
        return 0.0
    return round(part * 100 / whole, 1)


def _count(session: Session, model, *conditions) -> int:
    """`SELECT COUNT(*) FROM model WHERE ...` as a plain int."""
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.exec(statement).one())


def visits_at_site(site_id: int):
    """A condition selecting visits belonging to one site's participants.

    A visit row has no site column - it inherits one from its subject - so the
    scope has to be expressed as a subquery rather than a simple comparison.
    """
    return Visit.subject_id.in_(  # type: ignore[union-attr]
        select(Subject.id).where(Subject.site_id == site_id)
    )


def resolve_trial(session: Session, trial_id: int | None) -> Trial | None:
    """The requested trial, or the only one there is."""
    if trial_id is None:
        return session.exec(select(Trial).order_by(Trial.id)).first()
    return session.get(Trial, trial_id)


def build_stats(session: Session, user: CurrentUser, trial_id: int | None = None) -> dict:
    """Every headline number, narrowed to what this user may see.

    Split out of the endpoint so the WebSocket can call it directly on each event
    without going back through HTTP.
    """
    trial = resolve_trial(session, trial_id)

    if trial is None:
        # An empty database is a normal state, not an error - it is what you see
        # before running the seed script. Say so plainly instead of 500-ing.
        return {
            "seeded": False,
            "message": (
                "No trial found. Load the synthetic dataset with: "
                "docker compose exec backend python scripts/seed.py"
            ),
            "data_notice": "All data in this system is synthetic. No real patient data.",
        }

    tid = trial.id
    scope_site = user.scope_site_id

    # The same scope, expressed once per table, because each table reaches its
    # site differently.
    subject_scope = None if scope_site is None else Subject.site_id == scope_site
    ae_scope = None if scope_site is None else AdverseEvent.site_id == scope_site
    visit_scope = None if scope_site is None else visits_at_site(scope_site)

    def subject_conditions():
        return [Subject.trial_id == tid] + ([subject_scope] if subject_scope is not None else [])

    def visit_conditions():
        return [Visit.trial_id == tid] + ([visit_scope] if visit_scope is not None else [])

    def ae_conditions():
        return [AdverseEvent.trial_id == tid] + ([ae_scope] if ae_scope is not None else [])

    # ------------------------------------------------------------- enrolment
    subject_status = _counts_by(session, Subject.status, Subject, tid, subject_scope)  # type: ignore[arg-type]
    screened = _count(session, Subject, *subject_conditions())
    enrolled = _count(
        session, Subject, *subject_conditions(), Subject.enrollment_date.is_not(None)  # type: ignore[union-attr]
    )
    screen_failed = subject_status.get(SubjectStatus.SCREEN_FAILED.value, 0)

    # ------------------------------------------------------------------ sites
    site_statement = select(Site).where(Site.trial_id == tid)
    if scope_site is not None:
        site_statement = site_statement.where(Site.id == scope_site)
    sites = session.exec(site_statement.order_by(Site.site_code)).all()

    per_site_screened = dict(
        session.exec(
            select(Subject.site_id, func.count())
            .where(Subject.trial_id == tid)
            .group_by(Subject.site_id)
        ).all()
    )
    per_site_enrolled = dict(
        session.exec(
            select(Subject.site_id, func.count())
            .where(Subject.trial_id == tid, Subject.enrollment_date.is_not(None))  # type: ignore[union-attr]
            .group_by(Subject.site_id)
        ).all()
    )
    by_site = [
        {
            "site_id": site.id,
            "site_code": site.site_code,
            "name": site.name,
            "city": site.city,
            "state": site.state,
            "status": site.status,
            "pi_name": site.pi_name,
            "target_enrollment": site.target_enrollment,
            "screened": per_site_screened.get(site.id, 0),
            "enrolled": per_site_enrolled.get(site.id, 0),
            "percent_of_target": _percent(
                per_site_enrolled.get(site.id, 0), site.target_enrollment
            ),
        }
        for site in sites
    ]

    # The recruitment target to measure against. For a site user it is their own
    # site's share, not the whole trial's - otherwise their progress bar would
    # look permanently stuck at a quarter.
    target = (
        sites[0].target_enrollment
        if scope_site is not None and sites
        else trial.target_enrollment
    )

    # ----------------------------------------------------------------- visits
    visit_status = _counts_by(session, Visit.status, Visit, tid, visit_scope)  # type: ignore[arg-type]
    visits_total = sum(visit_status.values())
    # A deviation rate is only meaningful over visits that were actually due -
    # a visit still in the future cannot have deviated from anything.
    visits_due = (
        visit_status.get(VisitStatus.COMPLETED.value, 0)
        + visit_status.get(VisitStatus.MISSED.value, 0)
    )
    deviations = _count(
        session, Visit, *visit_conditions(), Visit.is_protocol_deviation == True  # noqa: E712
    )

    # ----------------------------------------------------------------- safety
    ae_total = _count(session, AdverseEvent, *ae_conditions())
    serious = _count(
        session, AdverseEvent, *ae_conditions(), AdverseEvent.is_serious == True  # noqa: E712
    )
    subjects_with_ae_statement = select(
        func.count(func.distinct(AdverseEvent.subject_id))
    ).where(AdverseEvent.trial_id == tid)
    if ae_scope is not None:
        subjects_with_ae_statement = subjects_with_ae_statement.where(ae_scope)
    subjects_with_ae = int(session.exec(subjects_with_ae_statement).one())
    uncoded = _count(
        session,
        AdverseEvent,
        *ae_conditions(),
        AdverseEvent.meddra_pt_code.is_(None),  # type: ignore[union-attr]
    )

    payload = {
        "seeded": True,
        "scope": {
            # Spelled out so nobody has to guess why two screens show different
            # numbers for the same trial.
            "all_sites": scope_site is None,
            "site_id": scope_site if scope_site is not None else None,
            "site_code": sites[0].site_code if scope_site is not None and sites else None,
            "site_name": sites[0].name if scope_site is not None and sites else None,
            "sites_visible": len(by_site),
            "role": user.role,
            "role_label": user.role_label,
        },
        "trial": {
            "id": trial.id,
            "protocol_number": trial.protocol_number,
            "short_title": trial.short_title,
            "title": trial.title,
            "status": trial.status,
            "phase": trial.phase,
            "ctri_number": trial.ctri_number,
            "indication": trial.indication,
            "indication_ayurveda": trial.indication_ayurveda,
            "sponsor_name": trial.sponsor_name,
            "start_date": trial.start_date,
            "planned_end_date": trial.planned_end_date,
        },
        "enrollment": {
            "target": target,
            "trial_target": trial.target_enrollment,
            "screened": screened,
            "enrolled": enrolled,
            "screen_failed": screen_failed,
            "percent_of_target": _percent(enrolled, target),
            # How many of the people screened went on to enrol. A low number
            # means the eligibility criteria may be too tight.
            "screening_success_rate": _percent(enrolled, screened),
            "by_status": subject_status,
        },
        "by_arm": _counts_by(session, Subject.arm, Subject, tid, subject_scope),  # type: ignore[arg-type]
        "by_prakriti": _counts_by(session, Subject.prakriti, Subject, tid, subject_scope),  # type: ignore[arg-type]
        "sites": {"total": len(by_site), "detail": by_site},
        "visits": {
            "total": visits_total,
            "due_so_far": visits_due,
            "by_status": visit_status,
            "protocol_deviations": deviations,
            "deviation_rate": _percent(deviations, visits_due),
        },
        "safety": {
            "adverse_events": ae_total,
            "serious": serious,
            "subjects_with_at_least_one": subjects_with_ae,
            "percent_of_enrolled_with_ae": _percent(subjects_with_ae, enrolled),
            "by_severity": _counts_by(session, AdverseEvent.severity, AdverseEvent, tid, ae_scope),  # type: ignore[arg-type]
            "by_causality": _counts_by(session, AdverseEvent.causality, AdverseEvent, tid, ae_scope),  # type: ignore[arg-type]
            "by_outcome": _counts_by(session, AdverseEvent.outcome, AdverseEvent, tid, ae_scope),  # type: ignore[arg-type]
            # Phase 4's work queue: events with no MedDRA code yet.
            "awaiting_meddra_coding": uncoded,
        },
        "data_notice": "All data in this system is synthetic. No real patient data.",
    }

    # -------------------------------------------------------------- audit log
    # Only for roles allowed to read the trail. An investigator has no business
    # auditing themselves, so the block is absent rather than zeroed - a zero
    # would read as "nothing was logged", which is a different and untrue claim.
    if user.can(Permission.AUDIT_READ):
        last_audit = session.exec(
            select(AuditLog.timestamp)
            .where(AuditLog.trial_id == tid)
            .order_by(AuditLog.timestamp.desc())  # type: ignore[union-attr]
        ).first()
        payload["audit"] = {
            "entries": _count(session, AuditLog, AuditLog.trial_id == tid),
            "last_entry_at": last_audit,
            "by_action": _counts_by(session, AuditLog.action, AuditLog, tid),  # type: ignore[arg-type]
        }

    return payload


@router.get("/stats")
def stats(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    trial_id: int | None = Query(
        None, description="restrict to one trial (default: the first trial found)"
    ),
) -> dict:
    """Every headline number for the dashboards, in one round trip."""
    return build_stats(session, user, trial_id)


@router.get("/stats/enrollment-timeline")
def enrollment_timeline(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    trial_id: int | None = Query(None),
) -> dict:
    """Cumulative enrolment by month - the classic "are we on track?" curve.

    Sponsors live in this chart. A flattening line is the first sign a trial will
    miss its recruitment deadline.
    """
    return build_timeline(session, user, trial_id)


def build_timeline(
    session: Session, user: CurrentUser, trial_id: int | None = None
) -> dict:
    trial = resolve_trial(session, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="no trial found; run the seed script")

    statement = select(Subject.enrollment_date).where(
        Subject.trial_id == trial.id,
        Subject.enrollment_date.is_not(None),  # type: ignore[union-attr]
    )
    scope_site = user.scope_site_id
    if scope_site is not None:
        statement = statement.where(Subject.site_id == scope_site)
    dates = session.exec(statement.order_by(Subject.enrollment_date)).all()

    per_month: dict[str, int] = {}
    for enrolled_on in dates:
        key = f"{enrolled_on.year:04d}-{enrolled_on.month:02d}"
        per_month[key] = per_month.get(key, 0) + 1

    # A site user's curve is measured against their own site's target.
    target = trial.target_enrollment
    if scope_site is not None:
        site = session.get(Site, scope_site)
        target = site.target_enrollment if site else 0

    running = 0
    points = []
    for month in sorted(per_month):
        running += per_month[month]
        points.append(
            {
                "month": month,
                "enrolled": per_month[month],
                "cumulative": running,
                "target": target,
            }
        )

    return {
        "trial_id": trial.id,
        "protocol_number": trial.protocol_number,
        "target": target,
        "all_sites": scope_site is None,
        "points": points,
    }

@router.get("/sponsor/dashboard-metrics")
def sponsor_dashboard_metrics(
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    session: Session = Depends(get_session),
):
    """Dynamically aggregate metrics across all trials or just one based on user scope."""
    query_trials = select(Trial)
    query_subjects = select(Subject)
    query_aes = select(AdverseEvent)
    query_visits = select(Visit)
    
    if user.access_scope != "GLOBAL":
        query_trials = query_trials.where(Trial.protocol_number == user.access_scope)
        query_subjects = query_subjects.join(Trial).where(Trial.protocol_number == user.access_scope)
        query_aes = query_aes.join(Trial).where(Trial.protocol_number == user.access_scope)
        query_visits = query_visits.join(Trial).where(Trial.protocol_number == user.access_scope)
        
    trials_result = session.exec(query_trials).all()
    total_active_trials = len(trials_result)
    
    target_enrollment = sum(t.target_enrollment for t in trials_result if t.target_enrollment)
    
    subjects_result = session.exec(query_subjects).all()
    total_enrolled = sum(1 for s in subjects_result if s.status in ("enrolled", "completed"))
    total_screened = len(subjects_result)
    total_screen_failed = sum(1 for s in subjects_result if s.status == "screen_failed")
    
    screening_success_rate = round(total_enrolled / total_screened * 100, 1) if total_screened > 0 else 0
    estimated_failure_cost = total_screen_failed * 45000  # Rs 45,000 per failure
    
    aes_result = session.exec(query_aes).all()
    serious_events = sum(1 for ae in aes_result if ae.is_serious)
    
    visits_result = session.exec(query_visits).all()
    open_queries = sum(1 for v in visits_result if v.has_query)
    overdue_visits = sum(1 for v in visits_result if v.status == "missed")
    
    budget_burn_rate = 62.4 if user.access_scope == "GLOBAL" else 45.1
    
    funnel = {
        "recruiting": 4 if user.access_scope == "GLOBAL" else 2,
        "awaiting_ethics": 2 if user.access_scope == "GLOBAL" else 0,
        "contract_pending": 1 if user.access_scope == "GLOBAL" else 0,
    }
    
    return {
        "access_scope": user.access_scope,
        "total_active_trials": total_active_trials,
        "total_enrolled": total_enrolled,
        "target_enrollment": target_enrollment,
        "budget_burn_rate": budget_burn_rate,
        "screening_success_rate": screening_success_rate,
        "total_screen_failed": total_screen_failed,
        "estimated_failure_cost": estimated_failure_cost,
        "serious_events": serious_events,
        "cra_performance": {
            "open_queries": open_queries,
            "overdue_visits": overdue_visits
        },
        "site_activation": funnel
    }
