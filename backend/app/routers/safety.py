"""Adverse events - the safety side of the trial.

Two words that sound alike and are not:

  severity     how intense it was: mild, moderate, severe.
  seriousness  a regulatory category: death, life-threatening, hospitalisation,
               disability, or a birth defect.

A severe headache is not serious. A mild reaction that puts someone in hospital
overnight is. Seriousness is what starts a reporting clock, which is why
`is_serious` is its own indexed column and not a severity level.

Phase 4 layers the NLP on top of these same rows: it reads `description`, fills
in the MedDRA codes, and watches for clusters.

Phase 2 scoping: an investigator or coordinator sees their own site's events. The
Ethics Committee and the Regulator see all of them - reviewing safety across every
site is precisely their job.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select

from app.db import get_session
from app.models import AdverseEvent, Site, Subject, Trial
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate
from app.services.safety_report import SafetyCaseReportData, build_safety_case_pdf
from app.services.safety_signals import (
    SignalEvent,
    SignalSite,
    calculate_safety_signals,
)

router = APIRouter(prefix="/api", tags=["safety"])


@router.get("/trials/{trial_id}/safety-signals")
def trial_safety_signals(
    trial_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_READ)),
) -> dict:
    """Calculate demo PRR signals for each visible Site and verbatim AE term."""
    if session.get(Trial, trial_id) is None:
        raise HTTPException(status_code=404, detail=f"trial {trial_id} not found")

    site_statement = select(Site).where(Site.trial_id == trial_id)
    site_statement = scoped(site_statement, Site.id, user)
    sites = session.exec(site_statement).all()
    events = session.exec(
        select(AdverseEvent).where(AdverseEvent.trial_id == trial_id)
    ).all()

    return calculate_safety_signals(
        trial_id,
        (
            SignalSite(id=site.id, code=site.site_code, name=site.name)
            for site in sites
            if site.id is not None
        ),
        (
            SignalEvent(site_id=event.site_id, term=event.term_verbatim)
            for event in events
        ),
    )


@router.get("/adverse-events/{event_id}/safety-report.pdf")
def export_adverse_event_safety_report(
    event_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.EXPORT)),
) -> Response:
    """Download a de-identified, non-validated demo safety-case PDF."""
    event = session.get(AdverseEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=404, detail=f"no adverse event with id {event_id}"
        )
    assert_site_visible(user, event.site_id)

    subject = session.get(Subject, event.subject_id)
    site = session.get(Site, event.site_id)
    trial = session.get(Trial, event.trial_id)
    if (
        subject is None
        or site is None
        or trial is None
        or site.trial_id != event.trial_id
        or subject.trial_id != event.trial_id
        or subject.site_id != event.site_id
    ):
        raise HTTPException(
            status_code=409,
            detail="adverse event has inconsistent trial, site, or subject linkage",
        )

    report = SafetyCaseReportData(
        protocol_number=trial.protocol_number,
        trial_title=trial.title,
        ctri_number=trial.ctri_number,
        sponsor_name=trial.sponsor_name,
        site_code=site.site_code,
        site_name=site.name,
        site_location=f"{site.city}, {site.state}, {site.country}",
        subject_code=subject.subject_code,
        subject_sex=subject.sex,
        subject_age_at_enrollment=subject.age_at_enrollment,
        study_arm=subject.arm,
        ae_number=event.ae_number,
        term_verbatim=event.term_verbatim,
        description=event.description,
        onset_date=event.onset_date,
        resolution_date=event.resolution_date,
        severity=event.severity,
        is_serious=event.is_serious,
        seriousness_criteria=event.seriousness_criteria,
        causality=event.causality,
        outcome=event.outcome,
        action_taken=event.action_taken,
        meddra_pt_code=event.meddra_pt_code,
        meddra_pt_term=event.meddra_pt_term,
        meddra_soc=event.meddra_soc,
        coding_confidence=event.coding_confidence,
        reported_date=event.reported_date,
        reported_to_ec=event.reported_to_ec,
        reported_to_ec_date=event.reported_to_ec_date,
    )
    pdf = build_safety_case_pdf(report)
    filename = f"safety-report-{event.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

from datetime import date, datetime, timedelta
from sqlmodel import SQLModel


class AdverseEventPublic(SQLModel):
    id: int
    trial_id: int
    site_id: int
    subject_id: int
    ae_number: str
    term_verbatim: str
    description: str | None = None
    onset_date: date
    resolution_date: date | None = None
    severity: str
    is_serious: bool
    seriousness_criteria: str | None = None
    causality: str
    outcome: str
    action_taken: str | None = None
    meddra_pt_code: str | None = None
    meddra_pt_term: str | None = None
    meddra_soc: str | None = None
    coding_confidence: float | None = None
    reported_date: date | None = None
    reported_to_ec: bool = False
    reported_to_ec_date: date | None = None
    created_at: datetime
    updated_at: datetime

    # NPvCC / NDCT Rules 2019 Rule 42 Regulatory Timeline Fields
    expedited_deadline: date | None = None
    detailed_report_deadline: date | None = None
    regulatory_urgency: str | None = None


def _hydrate_adverse_event(
    event: AdverseEvent, today: date | None = None
) -> AdverseEventPublic:
    eval_date = today or date.today()
    expedited_deadline = None
    detailed_deadline = None
    urgency = None

    if event.is_serious and event.onset_date:
        expedited_deadline = event.onset_date + timedelta(days=1)
        detailed_deadline = event.onset_date + timedelta(days=14)

        if event.reported_to_ec:
            urgency = "COMPLIANT_SUBMITTED"
        elif eval_date > expedited_deadline:
            urgency = "EXPEDITED_OVERDUE"
        elif eval_date == expedited_deadline or eval_date == event.onset_date:
            urgency = "EXPEDITED_DUE_SOON"
        else:
            urgency = "EXPEDITED_PENDING"
    elif event.is_serious:
        urgency = "EXPEDITED_PENDING"
    else:
        urgency = "NON_SERIOUS"

    dto = AdverseEventPublic.model_validate(event, from_attributes=True)
    dto.expedited_deadline = expedited_deadline
    dto.detailed_report_deadline = detailed_deadline
    dto.regulatory_urgency = urgency
    return dto


@router.get("/adverse-events", response_model=Page[AdverseEventPublic])
def list_adverse_events(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_READ)),
    trial_id: int | None = Query(None),
    site_id: int | None = Query(None),
    subject_id: int | None = Query(None),
    severity: str | None = Query(None, description="mild, moderate, severe"),
    serious_only: bool = Query(
        False, description="only events meeting a regulatory seriousness criterion"
    ),
    causality: str | None = Query(
        None, description="unrelated, unlikely, possible, probable, definite"
    ),
    uncoded_only: bool = Query(
        False, description="only events with no MedDRA code yet (Phase 4 work queue)"
    ),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[AdverseEventPublic]:
    # Newest first: a safety reviewer cares about what just came in.
    statement = select(AdverseEvent).order_by(AdverseEvent.onset_date.desc())  # type: ignore[union-attr]
    if trial_id is not None:
        statement = statement.where(AdverseEvent.trial_id == trial_id)
    if site_id is not None:
        statement = statement.where(AdverseEvent.site_id == site_id)
    if subject_id is not None:
        statement = statement.where(AdverseEvent.subject_id == subject_id)
    if severity:
        statement = statement.where(AdverseEvent.severity == severity)
    if serious_only:
        statement = statement.where(AdverseEvent.is_serious == True)  # noqa: E712
    if causality:
        statement = statement.where(AdverseEvent.causality == causality)
    if uncoded_only:
        statement = statement.where(AdverseEvent.meddra_pt_code.is_(None))  # type: ignore[union-attr]
    statement = scoped(statement, AdverseEvent.site_id, user)
    total, items = paginate(session, statement, limit, offset)
    today = date.today()
    hydrated = [_hydrate_adverse_event(item, today) for item in items]
    return Page(total=total, limit=limit, offset=offset, items=hydrated)


from app import audit
from app.enums import AuditAction
from app.models.base import utcnow
import json
from pydantic import BaseModel, ConfigDict, Field


class AdverseEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trial_id: int
    site_id: int | None = None
    subject_id: int
    term_verbatim: str
    description: str | None = None
    onset_date: date
    resolution_date: date | None = None
    severity: str = "mild"
    is_serious: bool = False
    seriousness_criteria: str | None = None
    causality: str = "unrelated"
    outcome: str = "recovering"
    action_taken: str | None = None
    meddra_pt_code: str | None = None
    meddra_pt_term: str | None = None
    meddra_soc: str | None = None


@router.post("/adverse-events", response_model=AdverseEventPublic, status_code=201)
def create_adverse_event(
    body: AdverseEventCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_WRITE)),
) -> AdverseEventPublic:
    """Report a new clinical adverse event with MedDRA coding and seriousness criteria."""
    subject = session.get(Subject, body.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail=f"subject {body.subject_id} not found")

    site_id = body.site_id or subject.site_id
    assert_site_visible(user, site_id)

    count = list(session.exec(select(AdverseEvent).where(AdverseEvent.subject_id == body.subject_id)).all())
    seq = len(count) + 1
    sub_code_suffix = subject.subject_code.split("-")[-1] if "-" in subject.subject_code else str(subject.id)
    ae_num = f"AE-{sub_code_suffix}-{seq:02d}"

    now = utcnow()
    event = AdverseEvent(
        trial_id=body.trial_id,
        site_id=site_id,
        subject_id=body.subject_id,
        ae_number=ae_num,
        term_verbatim=body.term_verbatim.strip(),
        description=body.description.strip() if body.description else None,
        onset_date=body.onset_date,
        resolution_date=body.resolution_date,
        severity=body.severity.lower(),
        is_serious=body.is_serious,
        seriousness_criteria=body.seriousness_criteria.strip() if body.seriousness_criteria else None,
        causality=body.causality.lower(),
        outcome=body.outcome.lower(),
        action_taken=body.action_taken.strip() if body.action_taken else None,
        meddra_pt_code=body.meddra_pt_code,
        meddra_pt_term=body.meddra_pt_term,
        meddra_soc=body.meddra_soc,
        created_at=now,
        updated_at=now,
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="adverse_events",
        entity_id=event.id,
        entity_label=event.ae_number,
        field_name=None,
        old_value=None,
        new_value=json.dumps({"ae_number": event.ae_number, "term": event.term_verbatim, "is_serious": event.is_serious, "severity": event.severity}),
        reason=f"Adverse event reported for participant {subject.subject_code}",
    )

    return _hydrate_adverse_event(event)


@router.get("/adverse-events/{event_id}", response_model=AdverseEventPublic)
def get_adverse_event(
    event_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_READ)),
) -> AdverseEventPublic:
    event = session.get(AdverseEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"no adverse event with id {event_id}")
    assert_site_visible(user, event.site_id)
    return _hydrate_adverse_event(event)
