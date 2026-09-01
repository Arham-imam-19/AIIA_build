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

from pydantic import BaseModel, ConfigDict
from datetime import date
from app import audit
from app.enums import AuditAction
from app.events import bus
import json
from app.models.base import utcnow

router = APIRouter(prefix="/api", tags=["safety"])

class AdverseEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: int
    term_verbatim: str
    description: str | None = None
    severity: str
    is_serious: bool
    seriousness_criteria: str | None = None
    causality: str
    action_taken: str
    outcome: str
    onset_date: date | None = None

@router.post("/adverse-events", response_model=AdverseEvent, status_code=201)
def report_adverse_event(
    body: AdverseEventCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_WRITE)),
) -> AdverseEvent:
    subject = session.get(Subject, body.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    assert_site_visible(user, subject.site_id)
    
    # Generate AE Number
    count = session.exec(select(AdverseEvent).where(AdverseEvent.subject_id == subject.id)).all()
    ae_number = f"AE-{subject.subject_code}-{(len(count) + 1):02d}"

    now = utcnow()
    event = AdverseEvent(
        trial_id=subject.trial_id,
        site_id=subject.site_id,
        subject_id=subject.id,
        ae_number=ae_number,
        term_verbatim=body.term_verbatim,
        description=body.description,
        severity=body.severity,
        is_serious=body.is_serious,
        seriousness_criteria=body.seriousness_criteria,
        causality=body.causality,
        action_taken=body.action_taken,
        outcome=body.outcome,
        onset_date=body.onset_date,
        reported_date=now.date(),
        is_expected=False,
    )
    session.add(event)
    session.flush()

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="adverse_events",
        entity_id=event.id,
        entity_label=ae_number,
        reason=f"SAE Reported: {body.term_verbatim}" if body.is_serious else f"AE Reported: {body.term_verbatim}",
        trial_id=subject.trial_id,
    )
    session.commit()
    session.refresh(event)
    bus.broadcast(str(user.id), "dashboard_updated", {"message": "New adverse event reported"})
    return event
    
class AdverseEventMeddraUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meddra_llt: str | None = None
    meddra_llt_code: str | None = None
    meddra_pt: str | None = None
    meddra_pt_code: str | None = None
    meddra_soc: str | None = None
    meddra_soc_code: str | None = None

@router.patch("/adverse-events/{event_id}/meddra", response_model=AdverseEvent)
def update_meddra_coding(
    event_id: int,
    body: AdverseEventMeddraUpdate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_WRITE)),
) -> AdverseEvent:
    event = session.get(AdverseEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    old_value = json.dumps({"meddra_llt": event.meddra_llt, "meddra_pt": event.meddra_pt}, sort_keys=True)
    
    event.meddra_llt = body.meddra_llt
    event.meddra_llt_code = body.meddra_llt_code
    event.meddra_pt = body.meddra_pt
    event.meddra_pt_code = body.meddra_pt_code
    event.meddra_soc = body.meddra_soc
    event.meddra_soc_code = body.meddra_soc_code
    event.updated_at = utcnow()
    session.add(event)
    
    new_value = json.dumps({"meddra_llt": event.meddra_llt, "meddra_pt": event.meddra_pt}, sort_keys=True)
    audit.record(
        session,
        user=user,
        action=AuditAction.UPDATE,
        entity_type="adverse_events",
        entity_id=event.id,
        entity_label=event.ae_number,
        field_name="meddra_coding",
        old_value=old_value,
        new_value=new_value,
        reason=f"MedDRA coded as {event.meddra_pt}",
        trial_id=event.trial_id,
    )
    session.commit()
    session.refresh(event)
    bus.broadcast(str(user.id), "dashboard_updated", {"message": "Event MedDRA coded"})
    return event


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

@router.get("/adverse-events", response_model=Page[AdverseEvent])
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
) -> Page[AdverseEvent]:
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
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/adverse-events/{event_id}", response_model=AdverseEvent)
def get_adverse_event(
    event_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_READ)),
) -> AdverseEvent:
    event = session.get(AdverseEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"no adverse event with id {event_id}")
    assert_site_visible(user, event.site_id)
    return event
