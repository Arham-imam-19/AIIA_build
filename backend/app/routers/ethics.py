"""Ethics Committee (IEC) Adjudication & Safety Oversight Router.

Provides dedicated endpoints for individual Serious Adverse Event (SAE) review,
committee directives, regulatory compliance tracking, and permanent decision persistence.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app import audit
from app.db import get_session
from app.enums import AuditAction
from app.models import AdverseEvent, Site, Subject, Trial
from app.models.base import utcnow
from app.rbac import CurrentUser, Permission, require
from app.routers.stats import resolve_trial

router = APIRouter(prefix="/api/ethics", tags=["ethics"])


class SaeAdjudicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str  # "accepted", "rejected", "action_required", "pending"
    notes: str | None = None
    decision_date: date | None = None


@router.get("/sae-docket")
def get_ethics_sae_docket(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_READ)),
    trial_id: int | None = Query(None, description="restrict to one trial"),
) -> dict:
    """Retrieve full Serious Adverse Event (SAE) review docket for Ethics Committee adjudication."""
    trial = resolve_trial(session, trial_id)
    if trial is None:
        return {"unreviewed_count": 0, "reviewed_count": 0, "total_sae_count": 0, "saes": []}

    tid = trial.id
    now = datetime.now(timezone.utc)

    statement = (
        select(AdverseEvent, Subject.subject_code, Site.site_code, Site.name)
        .join(Subject, AdverseEvent.subject_id == Subject.id)
        .join(Site, AdverseEvent.site_id == Site.id)
        .where(AdverseEvent.trial_id == tid, AdverseEvent.is_serious == True)
        .order_by(AdverseEvent.created_at.desc())
    )

    results = session.exec(statement).all()

    saes = []
    unreviewed_count = 0
    reviewed_count = 0

    for ae, sub_code, site_code, site_name in results:
        created_at_utc = (
            ae.created_at.replace(tzinfo=timezone.utc)
            if ae.created_at.tzinfo is None
            else ae.created_at
        )
        elapsed_hours = (now - created_at_utc).total_seconds() / 3600.0
        hours_remaining = max(0.0, 24.0 - elapsed_hours)

        is_reported = bool(ae.reported_to_ec or ae.ec_decision)
        if ae.ec_decision:
            clock_status = "REPORTED_TO_EC"
            clock_label = f"Adjudicated ({ae.ec_decision.upper()})"
            tone = "good"
        elif ae.reported_to_ec:
            clock_status = "REPORTED_TO_EC"
            clock_label = f"Reported ({ae.reported_to_ec_date})"
            tone = "good"
        elif elapsed_hours > 24.0:
            clock_status = "OVERDUE"
            clock_label = f"OVERDUE ({round(elapsed_hours - 24.0, 1)}h past 24h deadline)"
            tone = "bad"
        elif elapsed_hours >= 18.0:
            clock_status = "DUE_SOON"
            clock_label = f"DUE SOON ({round(hours_remaining, 1)}h remaining)"
            tone = "warn"
        else:
            clock_status = "WITHIN_WINDOW"
            clock_label = f"Within Window ({round(hours_remaining, 1)}h remaining)"
            tone = "neutral"

        decision = ae.ec_decision or "pending"
        if decision in {"accepted", "rejected", "action_required"}:
            reviewed_count += 1
        else:
            unreviewed_count += 1

        saes.append({
            "id": ae.id,
            "ae_number": ae.ae_number,
            "subject_code": sub_code,
            "site_code": site_code,
            "site_name": site_name,
            "term_verbatim": ae.term_verbatim,
            "description": ae.description,
            "severity": ae.severity,
            "seriousness_criteria": ae.seriousness_criteria or "Medically Significant",
            "causality": ae.causality,
            "outcome": ae.outcome,
            "onset_date": str(ae.onset_date),
            "reported_date": str(ae.reported_date) if ae.reported_date else None,
            "created_at": created_at_utc.isoformat(),
            "reported_to_ec": is_reported,
            "reported_to_ec_date": str(ae.reported_to_ec_date or ae.ec_decision_date) if (ae.reported_to_ec_date or ae.ec_decision_date) else None,
            "clock_status": clock_status,
            "clock_label": clock_label,
            "tone": tone,
            "ec_decision": decision,
            "ec_decision_date": str(ae.ec_decision_date) if ae.ec_decision_date else None,
            "ec_decision_notes": ae.ec_decision_notes,
            "is_reviewed": decision in {"accepted", "rejected", "action_required"},
        })

    return {
        "trial_id": tid,
        "protocol_number": trial.protocol_number,
        "title": trial.short_title or trial.title,
        "unreviewed_count": unreviewed_count,
        "reviewed_count": reviewed_count,
        "total_sae_count": len(saes),
        "saes": saes,
    }


@router.post("/sae-docket/{event_id}/adjudicate")
def adjudicate_sae(
    event_id: int,
    body: SaeAdjudicationRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.ETHICS_WRITE)),
) -> dict:
    """Submit an official Institutional Ethics Committee (IEC) ruling on an individual SAE."""
    event = session.get(AdverseEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Adverse event {event_id} not found")

    clean_decision = body.decision.lower().strip()
    if clean_decision not in {"accepted", "rejected", "action_required", "pending"}:
        raise HTTPException(
            status_code=422,
            detail="Decision must be one of: 'accepted', 'rejected', 'action_required', 'pending'",
        )

    old_decision = event.ec_decision
    now = utcnow()
    event.ec_decision = clean_decision
    event.ec_decision_date = body.decision_date or now.date()
    event.ec_decision_notes = body.notes.strip() if body.notes else None
    event.ec_reviewed_by_user_id = user.id
    event.reported_to_ec = True
    if not event.reported_to_ec_date:
        event.reported_to_ec_date = event.ec_decision_date
    event.updated_at = now

    session.add(event)
    session.flush()

    audit.record(
        session,
        user=user,
        action=AuditAction.UPDATE,
        entity_type="adverse_events",
        entity_id=event.id,
        entity_label=event.ae_number,
        field_name="ec_decision",
        old_value=old_decision,
        new_value=json.dumps({
            "ec_decision": event.ec_decision,
            "ec_decision_date": str(event.ec_decision_date),
            "ec_decision_notes": event.ec_decision_notes,
            "adjudicated_by": user.email,
        }),
        reason=f"IEC Formal Adjudication: {event.ec_decision.upper()}. Directive: {event.ec_decision_notes or 'Standard Clinical Surveillance'}",
        trial_id=event.trial_id,
    )
    session.commit()
    session.refresh(event)

    return {
        "event_id": event.id,
        "ae_number": event.ae_number,
        "ec_decision": event.ec_decision,
        "ec_decision_date": str(event.ec_decision_date),
        "ec_decision_notes": event.ec_decision_notes,
        "status": "success",
    }
