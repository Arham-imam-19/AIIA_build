"""Trials and the sites that run them.

Phase 2 added the guard on each endpoint. A Principal Investigator or Coordinator
sees only their own hospital in `/api/sites`, and asking for another site's row by
id is a 403 rather than an empty answer - see `app/rbac.py` for why that
distinction matters.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from app import audit
from app.db import get_session
from app.enums import AuditAction, EthicsApprovalStatus, TrialStatus
from app.events import bus, now_iso
from app.models import Site, Subject, Trial, User
from app.models.base import utcnow
from app.services import trial_compliance
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate

router = APIRouter(prefix="/api", tags=["trials"])


class TrialEthicsApprovalUpdate(BaseModel):
    """The complete target state for a trial's ethics approval."""

    model_config = ConfigDict(extra="forbid")

    ethics_approval_status: EthicsApprovalStatus
    ethics_approval_number: str | None
    ethics_approval_date: date | None
    ethics_approval_valid_until: date | None


class TrialEthicsApprovalResponse(BaseModel):
    trial_id: int
    protocol_number: str
    ethics_approval_status: EthicsApprovalStatus
    ethics_approval_number: str | None
    ethics_approval_date: date | None
    ethics_approval_valid_until: date | None
    updated_at: datetime


class TrialCTRIRegistrationUpdate(BaseModel):
    """The complete target state for a trial's CTRI registration."""

    model_config = ConfigDict(extra="forbid")

    ctri_number: str | None
    ctri_registration_date: date | None


class TrialCTRIRegistrationResponse(BaseModel):
    trial_id: int
    protocol_number: str
    ctri_number: str | None
    ctri_registration_date: date | None
    updated_at: datetime


class TrialRegulatoryApprovalUpdate(BaseModel):
    """The complete target state for a trial's regulatory approval."""

    model_config = ConfigDict(extra="forbid")

    regulatory_approval_number: str | None
    regulatory_approval_date: date | None


class TrialRegulatoryApprovalResponse(BaseModel):
    trial_id: int
    protocol_number: str
    regulatory_approval_number: str | None
    regulatory_approval_date: date | None
    updated_at: datetime


class TrialActivationResponse(BaseModel):
    trial_id: int
    protocol_number: str
    current_status: TrialStatus
    activated_at: datetime
    activated_by_user_id: int
    updated_at: datetime


def _validate_ethics_approval(
    body: TrialEthicsApprovalUpdate, *, today: date
) -> str | None:
    """Validate one complete target state and return its trimmed number."""
    status = body.ethics_approval_status
    number = body.ethics_approval_number
    trimmed_number = number.strip() if number is not None else None
    approval_date = body.ethics_approval_date
    valid_until = body.ethics_approval_valid_until

    if status in {EthicsApprovalStatus.APPROVED, EthicsApprovalStatus.EXPIRED}:
        if not trimmed_number:
            raise HTTPException(
                status_code=422,
                detail="ethics approval number is required and must not be blank",
            )
        if approval_date is None:
            raise HTTPException(
                status_code=422, detail="ethics approval date is required"
            )
        if valid_until is None:
            raise HTTPException(
                status_code=422, detail="ethics approval validity date is required"
            )
        if approval_date > today:
            raise HTTPException(
                status_code=422, detail="ethics approval date must not be in the future"
            )
        if valid_until < approval_date:
            raise HTTPException(
                status_code=422,
                detail="ethics approval validity date must not precede the approval date",
            )
        if status is EthicsApprovalStatus.APPROVED and valid_until < today:
            raise HTTPException(
                status_code=422,
                detail="approved ethics approval validity date must not be in the past",
            )
        if status is EthicsApprovalStatus.EXPIRED and valid_until >= today:
            raise HTTPException(
                status_code=422,
                detail="expired ethics approval validity date must be before today",
            )
        return trimmed_number

    if number is not None or approval_date is not None or valid_until is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"ethics approval details must all be null when status is "
                f"'{status.value}'"
            ),
        )
    return None


def _ethics_state(trial: Trial) -> dict[str, str | None]:
    return {
        "status": trial.ethics_approval_status,
        "number": trial.ethics_approval_number,
        "approval_date": (
            str(trial.ethics_approval_date) if trial.ethics_approval_date else None
        ),
        "valid_until": (
            str(trial.ethics_approval_valid_until)
            if trial.ethics_approval_valid_until
            else None
        ),
    }


def _validate_ctri_registration(
    body: TrialCTRIRegistrationUpdate, *, trial: Trial, today: date
) -> str | None:
    """Validate one complete CTRI target state and return its trimmed number."""
    number = body.ctri_number
    trimmed_number = number.strip() if number is not None else None
    registration_date = body.ctri_registration_date

    if number is None and registration_date is None:
        return None
    if not trimmed_number:
        raise HTTPException(
            status_code=422,
            detail="CTRI number is required and must not be blank",
        )
    if registration_date is None:
        raise HTTPException(
            status_code=422,
            detail="CTRI registration date is required with a CTRI number",
        )
    if len(trimmed_number) > 80:
        raise HTTPException(
            status_code=422,
            detail="CTRI number must not exceed 80 characters",
        )
    if registration_date > today:
        raise HTTPException(
            status_code=422,
            detail="CTRI registration date must not be in the future",
        )
    if trial.start_date is not None and registration_date > trial.start_date:
        raise HTTPException(
            status_code=422,
            detail="CTRI registration date must not be after the trial start date",
        )
    return trimmed_number


def _ctri_state(
    number: str | None, registration_date: date | None
) -> dict[str, str | None]:
    return {
        "ctri_number": number,
        "ctri_registration_date": (
            str(registration_date) if registration_date is not None else None
        ),
    }


def _ctri_response(trial: Trial) -> TrialCTRIRegistrationResponse:
    assert trial.id is not None
    return TrialCTRIRegistrationResponse(
        trial_id=trial.id,
        protocol_number=trial.protocol_number,
        ctri_number=trial.ctri_number,
        ctri_registration_date=trial.ctri_registration_date,
        updated_at=trial.updated_at,
    )


def _validate_regulatory_approval(
    body: TrialRegulatoryApprovalUpdate, *, trial: Trial, today: date
) -> str | None:
    """Validate one complete regulatory target state and return its trimmed number."""
    number = body.regulatory_approval_number
    trimmed_number = number.strip() if number is not None else None
    approval_date = body.regulatory_approval_date

    if number is None and approval_date is None:
        return None
    if not trimmed_number:
        raise HTTPException(
            status_code=422,
            detail="regulatory approval number is required and must not be blank",
        )
    if approval_date is None:
        raise HTTPException(
            status_code=422,
            detail="regulatory approval date is required with an approval number",
        )
    if len(trimmed_number) > 120:
        raise HTTPException(
            status_code=422,
            detail="regulatory approval number must not exceed 120 characters",
        )
    if approval_date > today:
        raise HTTPException(
            status_code=422,
            detail="regulatory approval date must not be in the future",
        )
    if trial.start_date is not None and approval_date > trial.start_date:
        raise HTTPException(
            status_code=422,
            detail="regulatory approval date must not be after the trial start date",
        )
    return trimmed_number


def _regulatory_state(
    number: str | None, approval_date: date | None
) -> dict[str, str | None]:
    return {
        "regulatory_approval_number": number,
        "regulatory_approval_date": (
            str(approval_date) if approval_date is not None else None
        ),
    }


def _regulatory_response(trial: Trial) -> TrialRegulatoryApprovalResponse:
    assert trial.id is not None
    return TrialRegulatoryApprovalResponse(
        trial_id=trial.id,
        protocol_number=trial.protocol_number,
        regulatory_approval_number=trial.regulatory_approval_number,
        regulatory_approval_date=trial.regulatory_approval_date,
        updated_at=trial.updated_at,
    )


def _activation_response(trial: Trial) -> TrialActivationResponse:
    assert trial.id is not None
    assert trial.activated_at is not None
    assert trial.activated_by_user_id is not None
    return TrialActivationResponse(
        trial_id=trial.id,
        protocol_number=trial.protocol_number,
        current_status=TrialStatus(trial.status),
        activated_at=trial.activated_at,
        activated_by_user_id=trial.activated_by_user_id,
        updated_at=trial.updated_at,
    )


@router.get("/trials", response_model=Page[Trial])
def list_trials(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    status: str | None = Query(None, description="filter by trial status"),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Trial]:
    """The trial itself is visible to every role - a site investigator still needs
    to read the protocol they are running."""
    statement = select(Trial).order_by(Trial.protocol_number)
    if status:
        statement = statement.where(Trial.status == status)
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/trials/{trial_id}", response_model=Trial)
def get_trial(
    trial_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
) -> Trial:
    trial = session.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {trial_id}")
    return trial


@router.patch(
    "/trials/{trial_id}/ethics-approval",
    response_model=TrialEthicsApprovalResponse,
)
async def update_trial_ethics_approval(
    trial_id: int,
    body: TrialEthicsApprovalUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.ETHICS_WRITE)),
) -> TrialEthicsApprovalResponse:
    """Replace the complete ethics-approval state for one trial."""
    trial = session.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {trial_id}")

    now = utcnow()
    trimmed_number = _validate_ethics_approval(body, today=now.date())
    requested_state = (
        body.ethics_approval_status.value,
        trimmed_number,
        body.ethics_approval_date,
        body.ethics_approval_valid_until,
    )
    stored_state = (
        trial.ethics_approval_status,
        trial.ethics_approval_number,
        trial.ethics_approval_date,
        trial.ethics_approval_valid_until,
    )
    if requested_state == stored_state:
        return TrialEthicsApprovalResponse(
            trial_id=trial.id,
            protocol_number=trial.protocol_number,
            ethics_approval_status=EthicsApprovalStatus(trial.ethics_approval_status),
            ethics_approval_number=trial.ethics_approval_number,
            ethics_approval_date=trial.ethics_approval_date,
            ethics_approval_valid_until=trial.ethics_approval_valid_until,
            updated_at=trial.updated_at,
        )
    previous_state = _ethics_state(trial)

    trial.ethics_approval_status = body.ethics_approval_status.value
    trial.ethics_approval_number = trimmed_number
    trial.ethics_approval_date = body.ethics_approval_date
    trial.ethics_approval_valid_until = body.ethics_approval_valid_until
    trial.updated_at = now
    session.add(trial)

    action = {
        EthicsApprovalStatus.APPROVED: AuditAction.APPROVE,
        EthicsApprovalStatus.REJECTED: AuditAction.REJECT,
    }.get(body.ethics_approval_status, AuditAction.UPDATE)
    resulting_state = _ethics_state(trial)
    audit.record(
        session,
        user=user,
        action=action,
        entity_type="trials",
        entity_id=trial.id,
        entity_label=trial.protocol_number,
        field_name="ethics_approval",
        old_value=json.dumps(previous_state, sort_keys=True),
        new_value=json.dumps(resulting_state, sort_keys=True),
        reason=(
            "Trial ethics approval changed from "
            f"{previous_state['status'] or 'unset'} to "
            f"{body.ethics_approval_status.value}."
        ),
        trial_id=trial.id,
        request=request,
    )
    session.commit()
    session.refresh(trial)

    try:
        await bus.publish(
            {
                "type": "trial.ethics_updated",
                "at": now_iso(),
                "trial_id": trial.id,
                "status": trial.ethics_approval_status,
                "label": f"Ethics {trial.ethics_approval_status}",
                "message": f"Trial ethics approval updated to {trial.ethics_approval_status}.",
            }
        )
    except Exception:
        pass

    return TrialEthicsApprovalResponse(
        trial_id=trial.id,
        protocol_number=trial.protocol_number,
        ethics_approval_status=EthicsApprovalStatus(trial.ethics_approval_status),
        ethics_approval_number=trial.ethics_approval_number,
        ethics_approval_date=trial.ethics_approval_date,
        ethics_approval_valid_until=trial.ethics_approval_valid_until,
        updated_at=trial.updated_at,
    )


@router.patch(
    "/trials/{trial_id}/ctri-registration",
    response_model=TrialCTRIRegistrationResponse,
)
def update_trial_ctri_registration(
    trial_id: int,
    body: TrialCTRIRegistrationUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.CTRI_WRITE)),
) -> TrialCTRIRegistrationResponse:
    """Replace the complete CTRI registration state for one trial."""
    trial = session.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {trial_id}")

    now = utcnow()
    trimmed_number = _validate_ctri_registration(body, trial=trial, today=now.date())
    requested_state = (trimmed_number, body.ctri_registration_date)
    stored_state = (trial.ctri_number, trial.ctri_registration_date)
    if requested_state == stored_state:
        return _ctri_response(trial)

    if trial.activated_at is not None:
        raise HTTPException(
            status_code=409,
            detail="CTRI registration cannot be changed after trial activation",
        )

    if trimmed_number is not None:
        existing = session.exec(
            select(Trial).where(
                Trial.ctri_number == trimmed_number,
                Trial.id != trial_id,
            )
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="CTRI number is already assigned to another trial",
            )

    previous_state = _ctri_state(*stored_state)
    trial.ctri_number = trimmed_number
    trial.ctri_registration_date = body.ctri_registration_date
    trial.updated_at = now
    session.add(trial)

    resulting_state = _ctri_state(*requested_state)
    audit.record(
        session,
        user=user,
        action=AuditAction.UPDATE,
        entity_type="trials",
        entity_id=trial.id,
        entity_label=trial.protocol_number,
        field_name="ctri_number",
        old_value=json.dumps(previous_state, sort_keys=True, separators=(",", ":")),
        new_value=json.dumps(resulting_state, sort_keys=True, separators=(",", ":")),
        reason=(
            "Trial CTRI registration cleared."
            if trimmed_number is None
            else "Trial CTRI registration updated."
        ),
        trial_id=trial.id,
        request=request,
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="CTRI number is already assigned to another trial",
        ) from exc
    session.refresh(trial)
    return _ctri_response(trial)


@router.patch(
    "/trials/{trial_id}/regulatory-approval",
    response_model=TrialRegulatoryApprovalResponse,
)
def update_trial_regulatory_approval(
    trial_id: int,
    body: TrialRegulatoryApprovalUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.REGULATORY_WRITE)),
) -> TrialRegulatoryApprovalResponse:
    """Replace the complete regulatory-approval state for one trial."""
    trial = session.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {trial_id}")

    now = utcnow()
    trimmed_number = _validate_regulatory_approval(body, trial=trial, today=now.date())
    requested_state = (trimmed_number, body.regulatory_approval_date)
    stored_state = (
        trial.regulatory_approval_number,
        trial.regulatory_approval_date,
    )
    if requested_state == stored_state:
        return _regulatory_response(trial)

    if trial.activated_at is not None:
        raise HTTPException(
            status_code=409,
            detail="regulatory approval cannot be changed after trial activation",
        )

    previous_state = _regulatory_state(*stored_state)
    trial.regulatory_approval_number = trimmed_number
    trial.regulatory_approval_date = body.regulatory_approval_date
    trial.updated_at = now
    session.add(trial)

    resulting_state = _regulatory_state(*requested_state)
    audit.record(
        session,
        user=user,
        action=AuditAction.UPDATE,
        entity_type="trials",
        entity_id=trial.id,
        entity_label=trial.protocol_number,
        field_name="regulatory_approval_number",
        old_value=json.dumps(previous_state, sort_keys=True, separators=(",", ":")),
        new_value=json.dumps(resulting_state, sort_keys=True, separators=(",", ":")),
        reason=(
            "Trial regulatory approval cleared."
            if trimmed_number is None
            else "Trial regulatory approval updated."
        ),
        trial_id=trial.id,
        request=request,
    )
    session.commit()
    session.refresh(trial)
    return _regulatory_response(trial)


@router.post(
    "/trials/{trial_id}/activate",
    response_model=TrialActivationResponse,
)
def activate_trial(
    trial_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.ACTIVATION_WRITE)),
) -> TrialActivationResponse:
    """Activate one eligible trial for recruitment."""
    trial = session.exec(
        select(Trial).where(Trial.id == trial_id).with_for_update()
    ).one_or_none()
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {trial_id}")

    is_recruiting = trial.status == TrialStatus.RECRUITING.value
    has_activation_time = trial.activated_at is not None
    has_activation_actor = trial.activated_by_user_id is not None
    if is_recruiting and has_activation_time and has_activation_actor:
        return _activation_response(trial)
    if is_recruiting or has_activation_time or has_activation_actor:
        raise HTTPException(
            status_code=409,
            detail="trial activation state is inconsistent",
        )

    result = trial_compliance.check_activation_eligibility(trial)
    if not result.eligible_for_activation:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "trial is not eligible for activation",
                "blockers": [asdict(blocker) for blocker in result.blockers],
            },
        )

    previous_status = trial.status
    now = utcnow()
    old_state = {
        "status": previous_status,
        "activated_at": None,
        "activated_by_user_id": None,
    }
    trial.status = TrialStatus.RECRUITING.value
    trial.activated_at = now
    trial.activated_by_user_id = user.id
    trial.updated_at = now
    session.add(trial)
    new_state = {
        "status": trial.status,
        "activated_at": now.isoformat(),
        "activated_by_user_id": user.id,
    }

    try:
        audit.record(
            session,
            user=user,
            action=AuditAction.UPDATE,
            entity_type="trials",
            entity_id=trial.id,
            entity_label=trial.protocol_number,
            field_name="activation",
            old_value=json.dumps(old_state, sort_keys=True, separators=(",", ":")),
            new_value=json.dumps(new_state, sort_keys=True, separators=(",", ":")),
            reason=f"Trial activated from {previous_status} to recruiting.",
            trial_id=trial.id,
            request=request,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(trial)
    return _activation_response(trial)


@router.get("/trials/{trial_id}/compliance-status")
def get_trial_compliance_status(
    trial_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.COMPLIANCE_READ)),
) -> dict:
    """Return the existing read-only activation checks for one trial."""
    trial = session.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {trial_id}")

    result = trial_compliance.check_activation_eligibility(trial)
    compliance = asdict(result)
    compliance["eligibility"] = compliance.pop("eligible_for_activation")
    return {
        "trial_id": trial.id,
        "current_status": trial.status,
        **compliance,
    }


@router.get("/sites", response_model=Page[Site])
def list_sites(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SITE_READ)),
    trial_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Site]:
    statement = select(Site).order_by(Site.site_code)
    if trial_id is not None:
        statement = statement.where(Site.trial_id == trial_id)
    if status:
        statement = statement.where(Site.status == status)
    # A site user sees one site: their own. The scoping column here is the site's
    # own primary key rather than a site_id foreign key.
    statement = scoped(statement, Site.id, user)
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/sites/{site_id}", response_model=Site)
def get_site(
    site_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SITE_READ)),
) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"no site with id {site_id}")
    assert_site_visible(user, site.id)
    return site


@router.get("/sites/{site_id}/subjects", response_model=Page[Subject])
def list_site_subjects(
    site_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SITE_READ, Permission.SUBJECT_READ)),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Subject]:
    """The participants at one site.

    Needs both permissions: you must be allowed to see the site *and* to see
    participants. That is why an Ethics Committee member, who has site access but
    deliberately no participant access, gets 403 here.
    """
    if session.get(Site, site_id) is None:
        raise HTTPException(status_code=404, detail=f"no site with id {site_id}")
    assert_site_visible(user, site_id)
    statement = (
        select(Subject).where(Subject.site_id == site_id).order_by(Subject.subject_code)
    )
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


class CreateTrialRequest(SQLModel):
    protocol_number: str
    title: str
    short_title: str | None = None
    phase: str = "phase_2"
    indication: str
    indication_ayurveda: str | None = None
    intervention: str
    comparator: str | None = None
    design: str = "Randomized, Double-Blind, Parallel Group"
    sponsor_name: str = "All India Institute of Ayurveda"
    target_enrollment: int = 100


@router.post("/trials", response_model=Trial, status_code=201)
def create_trial(
    body: CreateTrialRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.USER_MANAGE)),
) -> Trial:
    """Primary Admin creates a new Clinical Trial protocol."""
    proto = body.protocol_number.strip().upper()
    existing = session.exec(select(Trial).where(Trial.protocol_number == proto)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"protocol {proto} already exists")

    now = utcnow()
    trial = Trial(
        protocol_number=proto,
        title=body.title.strip(),
        short_title=body.short_title.strip() if body.short_title else body.title.strip()[:180],
        phase=body.phase,
        status=TrialStatus.PLANNING.value,
        indication=body.indication.strip(),
        indication_ayurveda=body.indication_ayurveda.strip() if body.indication_ayurveda else None,
        intervention=body.intervention.strip(),
        comparator=body.comparator.strip() if body.comparator else None,
        design=body.design.strip(),
        is_blinded=True,
        sponsor_name=body.sponsor_name.strip(),
        target_enrollment=body.target_enrollment,
        ethics_approval_status=EthicsApprovalStatus.PENDING.value,
        created_at=now,
        updated_at=now,
    )
    session.add(trial)
    session.flush()

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="trials",
        entity_id=trial.id,
        entity_label=trial.protocol_number,
        reason=f"Clinical Trial Protocol {trial.protocol_number} created by Primary Admin",
        trial_id=trial.id,
    )
    session.commit()
    session.refresh(trial)
    return trial


class CreateSiteRequest(SQLModel):
    trial_id: int | None = None
    site_code: str
    name: str
    city: str
    state: str
    country: str = "India"
    pi_name: str
    pi_email: str | None = None
    contact_phone: str | None = None
    status: str = "activated"
    target_enrollment: int = 0


@router.post("/sites", response_model=Site, status_code=201)
def create_site(
    body: CreateSiteRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.INSTITUTION_MANAGE)),
) -> Site:
    """Primary Admin creates a new participating Institution / Site."""
    trial_id = body.trial_id
    if trial_id is None:
        first_trial = session.exec(select(Trial)).first()
        if first_trial is None:
            raise HTTPException(status_code=404, detail="no trial found to associate site with")
        trial_id = first_trial.id

    trial = session.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"trial {trial_id} not found")

    site_code = body.site_code.strip().upper()
    existing = session.exec(select(Site).where(Site.site_code == site_code, Site.trial_id == trial_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"site code {site_code} already exists for this trial")

    now = utcnow()
    site = Site(
        trial_id=trial_id,
        site_code=site_code,
        name=body.name.strip(),
        city=body.city.strip(),
        state=body.state.strip(),
        country=body.country.strip(),
        pi_name=body.pi_name.strip(),
        pi_email=body.pi_email.strip().lower() if body.pi_email else None,
        contact_phone=body.contact_phone.strip() if body.contact_phone else None,
        status=body.status,
        target_enrollment=body.target_enrollment,
        activation_date=now.date(),
        created_at=now,
    )
    session.add(site)
    session.flush()

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="sites",
        entity_id=site.id,
        entity_label=site.name,
        reason=f"Study site {site.site_code} ({site.name}) registered by {user.role_label}",
        trial_id=trial_id,
    )
    session.commit()
    session.refresh(site)
    return site



