"""Patient requests and communications to Institution Admins.

Provides a direct channel for trial participants (patients) to communicate with
hospital / institution administrators and coordinators. Patients can submit
inquiries regarding symptoms, medication, appointment reschedules, and grievances.
Institution Admins review, coordinate with researchers, and post official responses.
"""

from __future__ import annotations
from typing import Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session, select

from app import audit
from app.db import get_session
from app.enums import AuditAction, PatientRequestCategory, PatientRequestStatus, UserRole
from app.events import bus, now_iso
from app.models import PatientRequest, Site, Subject, User
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate
from app.services import privacy

router = APIRouter(prefix="/api/patient-requests", tags=["patient-requests"])


class CreatePatientRequest(BaseModel):
    category: PatientRequestCategory = Field(
        description="symptom_inquiry, appointment_reschedule, adverse_event_alert, medication_query, grievance, or general_inquiry"
    )
    subject_line: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5, max_length=3000)
    site_id: int | None = Field(
        default=None,
        description="Optional target institution if known",
    )


class RespondPatientRequest(BaseModel):
    response: str = Field(min_length=2, max_length=3000)
    status: Literal[
        PatientRequestStatus.IN_REVIEW.value,
        PatientRequestStatus.RESOLVED.value,
        PatientRequestStatus.ESCALATED.value,
    ] = Field(
        default=PatientRequestStatus.RESOLVED.value,
        description="in_review, resolved, or escalated",
    )


class PatientRequestPublic(BaseModel):
    id: int
    site_id: int
    site_name: str | None = None
    trial_id: int | None = None
    patient_user_id: int
    patient_name: str | None = None
    patient_email: str | None = None
    subject_id: int | None = None
    subject_code: str | None = None
    category: str
    subject_line: str
    message: str
    status: str
    assigned_admin_id: int | None = None
    assigned_admin_name: str | None = None
    admin_response: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


def _hydrate_request(session: Session, req: PatientRequest, user: CurrentUser | None = None) -> PatientRequestPublic:
    site = session.get(Site, req.site_id) if req.site_id else None
    patient = session.get(User, req.patient_user_id) if req.patient_user_id else None
    subject = session.get(Subject, req.subject_id) if req.subject_id else None
    admin = session.get(User, req.assigned_admin_id) if req.assigned_admin_id else None

    p_name = patient.full_name if patient else None
    p_email = patient.email if patient else None

    if user is not None and privacy.should_mask_patient_pii(user, req.site_id):
        p_name = privacy.mask_patient_name(p_name, subject.subject_code if subject else None)
        p_email = privacy.mask_email(p_email)

    return PatientRequestPublic(
        id=req.id,  # type: ignore[arg-type]
        site_id=req.site_id,
        site_name=site.name if site else None,
        trial_id=req.trial_id,
        patient_user_id=req.patient_user_id,
        patient_name=p_name,
        patient_email=p_email,
        subject_id=req.subject_id,
        subject_code=subject.subject_code if subject else None,
        category=req.category,
        subject_line=req.subject_line,
        message=req.message,
        status=req.status,
        assigned_admin_id=req.assigned_admin_id,
        assigned_admin_name=admin.full_name if admin else None,
        admin_response=req.admin_response,
        created_at=req.created_at,
        updated_at=req.updated_at,
        resolved_at=req.resolved_at,
    )


@router.get("", response_model=Page[PatientRequestPublic])
def list_patient_requests(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.PATIENT_REQUEST_READ)),
    status: str | None = Query(None, description="filter by status: submitted, in_review, resolved, escalated"),
    category: str | None = Query(None, description="filter by category"),
    site_id: int | None = Query(None),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[PatientRequestPublic]:
    statement = select(PatientRequest).order_by(PatientRequest.created_at.desc())

    # Patient can only view their own submitted requests
    if user.role == UserRole.PATIENT.value:
        statement = statement.where(PatientRequest.patient_user_id == user.id)
    else:
        # Scoped to site if user is institution admin / PI / coordinator
        statement = scoped(statement, PatientRequest.site_id, user)

    if status:
        statement = statement.where(PatientRequest.status == status)
    if category:
        statement = statement.where(PatientRequest.category == category)
    if site_id and (not user.is_site_scoped or user.site_id == site_id):
        statement = statement.where(PatientRequest.site_id == site_id)

    total, items = paginate(session, statement, limit, offset)
    hydrated = [_hydrate_request(session, req, user) for req in items]
    return Page(total=total, limit=limit, offset=offset, items=hydrated)


@router.post("", response_model=PatientRequestPublic, status_code=status.HTTP_201_CREATED)
async def create_patient_request(
    body: CreatePatientRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.PATIENT_REQUEST_WRITE)),
) -> PatientRequestPublic:
    """Submit a new patient inquiry or request directly to the Institution Admin."""
    # Determine the institution site_id
    target_site_id = user.site_id or body.site_id
    if target_site_id is None:
        # Fallback to first site
        first_site = session.exec(select(Site)).first()
        target_site_id = first_site.id if first_site else 1

    # Check for linked subject
    subject_id = user.subject_id
    trial_id = None
    if subject_id:
        subj = session.get(Subject, subject_id)
        if subj:
            trial_id = subj.trial_id
            target_site_id = subj.site_id

    req = PatientRequest(
        site_id=target_site_id,
        trial_id=trial_id,
        patient_user_id=user.id,
        subject_id=subject_id,
        category=body.category.value,
        subject_line=body.subject_line,
        message=body.message,
        status=PatientRequestStatus.SUBMITTED.value,
    )
    try:
        session.add(req)
        session.flush()

        audit.record(
            session,
            user=user,
            action=AuditAction.CREATE,
            entity_type="patient_requests",
            entity_id=req.id,
            entity_label=f"Request #{req.id}: {req.subject_line[:40]}",
            reason=f"Patient submitted {req.category} inquiry",
            trial_id=trial_id,
            request=request,
        )
        session.commit()
        session.refresh(req)
    except Exception:
        session.rollback()
        raise

    try:
        await bus.publish(
            {
                "type": "patient_request.created",
                "at": now_iso(),
                "trial_id": req.trial_id,
                "site_id": req.site_id,
                "subject_id": req.subject_id,
                "label": f"Request #{req.id}",
                "entity_id": req.id,
                "message": "A new patient inquiry was submitted.",
            }
        )
    except Exception:
        pass

    return _hydrate_request(session, req, user)


@router.get("/{request_id}", response_model=PatientRequestPublic)
def get_patient_request(
    request_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.PATIENT_REQUEST_READ)),
) -> PatientRequestPublic:
    req = session.get(PatientRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail=f"no request with id {request_id}")

    if user.role == UserRole.PATIENT.value and req.patient_user_id != user.id:
        raise HTTPException(status_code=403, detail="cannot view another patient's request")

    if user.is_site_scoped and user.role != UserRole.PATIENT.value:
        assert_site_visible(user, req.site_id)

    return _hydrate_request(session, req, user)


@router.patch("/{request_id}/respond", response_model=PatientRequestPublic)
async def respond_patient_request(
    request_id: int,
    body: RespondPatientRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.PATIENT_REQUEST_RESPOND)),
) -> PatientRequestPublic:
    """Respond to a patient request and update its status (Institution Admin / Super Admin)."""
    req = session.get(PatientRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail=f"no request with id {request_id}")

    if user.is_site_scoped:
        assert_site_visible(user, req.site_id)

    req.admin_response = body.response
    req.status = body.status
    req.assigned_admin_id = user.id
    req.updated_at = datetime.now(timezone.utc)
    if body.status == PatientRequestStatus.RESOLVED.value:
        req.resolved_at = datetime.now(timezone.utc)

    try:
        session.add(req)
        session.flush()

        audit.record(
            session,
            user=user,
            action=AuditAction.RESPOND,
            entity_type="patient_requests",
            entity_id=req.id,
            entity_label=f"Request #{req.id}: {req.subject_line[:40]}",
            reason=f"Admin responded and set status to {req.status}",
            trial_id=req.trial_id,
            request=request,
        )
        session.commit()
        session.refresh(req)
    except Exception:
        session.rollback()
        raise

    try:
        await bus.publish(
            {
                "type": "patient_request.updated",
                "at": now_iso(),
                "trial_id": req.trial_id,
                "site_id": req.site_id,
                "subject_id": req.subject_id,
                "label": f"Request #{req.id}",
                "entity_id": req.id,
                "message": f"Inquiry #{req.id} status was updated to {req.status}.",
            }
        )
    except Exception:
        pass

    return _hydrate_request(session, req, user)
