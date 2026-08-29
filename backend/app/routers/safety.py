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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import AdverseEvent, Site, Trial
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate
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
