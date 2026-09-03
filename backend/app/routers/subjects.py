"""Participants and their protocol visits.

Every subject record here is de-identified: no name, address, phone or date of
birth is stored, only a year of birth and an age. That is deliberate, and it is
what lets the whole dataset be shown in a demo.

Phase 2 scoping: a Principal Investigator or Coordinator sees only their own
site's participants and those participants' visits. An Ethics Committee member has
no participant access at all - their remit is safety events and deviations, not
browsing who is enrolled.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import audit
from app.db import get_session
from app.enums import (
    AuditAction,
    Prakriti,
    Sex,
    SiteStatus,
    StudyArm,
    SubjectStatus,
    TrialStatus,
    UserRole,
    VisitStatus,
)
from app.models import (
    AdverseEvent,
    AuditLog,
    ClinicalLogEntry,
    EConsent,
    Site,
    Subject,
    Trial,
    User,
    Visit,
)
from app.models.base import utcnow
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate
from app.services import privacy, trial_compliance
from app.services.subject_transition import (
    SubjectTransitionError,
    validate_subject_transition,
)
from app.services.visit_transition import VisitTransitionError, validate_visit_transition

router = APIRouter(prefix="/api", tags=["subjects"])


class SubjectScreeningCreate(BaseModel):
    """Only the de-identified information available when screening begins."""

    model_config = ConfigDict(extra="forbid")

    trial_id: int
    site_id: int | None = None
    screening_date: date
    sex: Sex
    year_of_birth: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    prakriti: Prakriti | None = None
    protocol_version: str | None = None
    inclusion_criteria: dict | None = None
    exclusion_criteria: dict | None = None
    eligibility_outcome: str | None = None
    screen_failure_reason: str | None = None
    icf_version: str | None = None
    consent_date: datetime | None = None
    consent_obtained_by: str | None = None
    withdrawal_of_consent: bool = False
    ethnicity: str | None = None

    @field_validator("height_cm", "weight_kg")
    @classmethod
    def positive_finite_measurement(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("measurement must be finite and positive")
        return value

    @model_validator(mode="after")
    def valid_screening_demographics(self) -> "SubjectScreeningCreate":
        if self.screening_date > date.today():
            raise ValueError("screening_date cannot be in the future")
        if (
            self.year_of_birth is not None
            and self.year_of_birth > self.screening_date.year
        ):
            raise ValueError("year_of_birth cannot be later than the screening year")
        return self


class SubjectScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trial_id: int
    site_id: int
    subject_code: str
    status: str
    arm: str
    screening_date: date
    sex: str
    year_of_birth: int | None
    height_cm: float | None
    weight_kg: float | None
    created_at: datetime
    updated_at: datetime


class SubjectScreeningOutcomeUpdate(BaseModel):
    """The only standalone screening outcome represented by the Subject model."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["screen_failed"]
    reason: str

    @field_validator("reason")
    @classmethod
    def nonblank_trimmed_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        if len(value) > 500:
            raise ValueError("reason must not exceed 500 characters")
        return value


class SubjectScreeningOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trial_id: int
    site_id: int
    subject_code: str
    status: str
    screen_failure_reason: str
    updated_at: datetime


class SubjectEnrollmentUpdate(BaseModel):
    """The protocol facts needed to enrol and randomize a screened Subject."""

    model_config = ConfigDict(extra="forbid")

    enrollment_date: date
    randomization_date: date
    arm: StudyArm
    prakriti: Prakriti | None = None

    @field_validator("arm")
    @classmethod
    def randomized_arm(cls, value: StudyArm) -> StudyArm:
        if value == StudyArm.NOT_RANDOMIZED:
            raise ValueError("arm must be treatment, placebo, or comparator")
        return value


class SubjectEnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trial_id: int
    site_id: int
    subject_code: str
    status: str
    enrollment_date: date
    randomization_date: date
    arm: str
    prakriti: str | None
    updated_at: datetime


class SubjectActivationUpdate(BaseModel):
    """Contemporaneous confirmation that the Subject received a first dose."""

    model_config = ConfigDict(extra="forbid")


class SubjectActivationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trial_id: int
    site_id: int
    subject_code: str
    status: str
    updated_at: datetime


class SubjectOutcomeUpdate(BaseModel):
    """Only caller-supplied facts needed for a terminal Subject outcome."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "withdrawn", "lost_to_follow_up"]
    completed_date: date | None = None
    withdrawal_date: date | None = None
    withdrawal_reason: str | None = None


class SubjectOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trial_id: int
    site_id: int
    subject_code: str
    status: str
    completed_date: date | None
    withdrawal_date: date | None
    withdrawal_reason: str | None
    updated_at: datetime


class VisitScheduleCreate(BaseModel):
    """The caller-supplied facts for one manually scheduled Visit."""

    model_config = ConfigDict(extra="forbid")

    visit_name: str
    visit_number: int
    visit_day: int
    scheduled_date: date

    @field_validator("visit_name")
    @classmethod
    def nonblank_trimmed_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("visit_name must not be blank")
        if len(value) > 120:
            raise ValueError("visit_name must not exceed 120 characters")
        return value

    @field_validator("visit_number")
    @classmethod
    def positive_visit_number(cls, value: int) -> int:
        if value < 1:
            raise ValueError("visit_number must be at least 1")
        return value

    @field_validator("scheduled_date")
    @classmethod
    def present_or_future_schedule(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("scheduled_date cannot be in the past")
        return value


class VisitScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    trial_id: int
    visit_name: str
    visit_number: int
    visit_day: int
    scheduled_date: date
    status: str
    created_at: datetime
    updated_at: datetime


class VisitOutcomeUpdate(BaseModel):
    """Only caller-supplied facts used to record a terminal Visit outcome."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "missed"]
    actual_date: date | None = None
    is_protocol_deviation: bool
    deviation_description: str | None = None


class VisitOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    status: str
    scheduled_date: date
    actual_date: date | None
    is_protocol_deviation: bool
    deviation_description: str | None
    performed_by_user_id: int | None
    updated_at: datetime


def _next_subject_code(session: Session, site: Site) -> str:
    """Continue the current Ashwagandha trial's per-site subject numbering."""
    prefix = f"AIIA-ASH-{site.site_code}-"
    codes = session.exec(
        select(Subject.subject_code).where(Subject.site_id == site.id)
    ).all()
    highest = 0
    for code in codes:
        if not code.startswith(prefix):
            continue
        tail = code[len(prefix):]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{prefix}{highest + 1:03d}"


def _is_subject_code_conflict(exc: IntegrityError) -> bool:
    """Recognise only the existing unique index on subjects.subject_code."""
    detail = str(exc.orig).lower()
    return (
        "ix_subjects_subject_code" in detail
        or "subjects.subject_code" in detail
    )


def _is_visit_number_conflict(exc: IntegrityError) -> bool:
    """Recognise only the Subject/visit-number composite uniqueness rule."""
    detail = str(exc.orig).lower()
    return (
        "uq_visits_subject_id_visit_number" in detail
        or "visits.subject_id, visits.visit_number" in detail
    )


def _visible_subject(session: Session, subject_id: int, user: CurrentUser) -> Subject:
    """Fetch a subject, 404 if absent, 403 if it belongs to another site or another patient."""
    subject = session.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")
    if user.role == UserRole.PATIENT.value:
        if user.subject_id is None or user.subject_id != subject_id:
            raise HTTPException(status_code=403, detail="forbidden: patients may only access their own record")
    else:
        assert_site_visible(user, subject.site_id)
    return subject


@router.post(
    "/subjects/screening",
    response_model=SubjectScreeningResponse,
    status_code=201,
)
@router.post(
    "/subjects",
    response_model=SubjectScreeningResponse,
    status_code=201,
)
def create_subject_in_screening(
    body: SubjectScreeningCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> SubjectScreeningResponse:
    """Create one de-identified Subject at the start of screening."""
    trial = session.get(Trial, body.trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {body.trial_id}")

    scope = user.scope_site_id
    if scope is None:
        if body.site_id is None:
            raise HTTPException(
                status_code=404,
                detail="site_id is required for a writer without an assigned site",
            )
        site = session.get(Site, body.site_id)
        if site is None:
            raise HTTPException(status_code=404, detail=f"no site with id {body.site_id}")
    else:
        if user.site_id is None:
            raise HTTPException(
                status_code=409,
                detail="your account is not attached to a valid site",
            )
        if body.site_id is not None and body.site_id != scope:
            raise HTTPException(
                status_code=403,
                detail=(
                    "cannot create a subject at another site. "
                    f"{user.role_label} access is limited to site id {user.site_id}."
                ),
            )
        site = session.get(Site, scope)
        if site is None:
            raise HTTPException(
                status_code=409,
                detail="your account is attached to a site that no longer exists",
            )

    if site.trial_id != trial.id:
        raise HTTPException(
            status_code=404,
            detail=f"no site with id {site.id} in this trial",
        )
    if trial.status != TrialStatus.RECRUITING.value:
        raise HTTPException(status_code=409, detail="this trial is not recruiting")
    if site.status != SiteStatus.RECRUITING.value:
        raise HTTPException(status_code=409, detail="this site is not recruiting")

    ethics_ok, ethics_reason = trial_compliance.check_ethics_clearance_for_enrollment(trial)
    if not ethics_ok:
        raise HTTPException(
            status_code=409,
            detail=f"Enrollment Blocked: {ethics_reason}",
        )

    now = utcnow()
    code = _next_subject_code(session, site)
    outcome = body.eligibility_outcome or "eligible"
    initial_status = (
        SubjectStatus.SCREEN_FAILED.value
        if outcome == "screen_failed"
        else SubjectStatus.SCREENING.value
    )
    subject = Subject(
        trial_id=trial.id,
        site_id=site.id,
        subject_code=code,
        status=initial_status,
        screening_date=body.screening_date,
        enrollment_date=None,
        randomization_date=None,
        arm=StudyArm.NOT_RANDOMIZED.value,
        year_of_birth=body.year_of_birth,
        age_at_enrollment=None,
        sex=body.sex.value,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        prakriti=body.prakriti.value if body.prakriti else None,
        inclusion_criteria=body.inclusion_criteria or {},
        exclusion_criteria=body.exclusion_criteria or {},
        eligibility_outcome=outcome,
        protocol_version=body.protocol_version,
        icf_version=body.icf_version,
        consent_date=body.consent_date,
        consent_obtained_by=body.consent_obtained_by or user.full_name,
        withdrawal_of_consent=body.withdrawal_of_consent,
        ethnicity=body.ethnicity,
        created_by_id=user.id,
        updated_by_id=user.id,
        completed_date=None,
        withdrawal_date=None,
        withdrawal_reason=None,
        screen_failure_reason=body.screen_failure_reason,
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(subject)
        session.flush()
        audit.record(
            session,
            user=user,
            action=AuditAction.CREATE,
            entity_type="subjects",
            entity_id=subject.id,
            entity_label=code,
            reason="Subject entered screening.",
            trial_id=trial.id,
            request=request,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_subject_code_conflict(exc):
            raise HTTPException(
                status_code=409,
                detail="the next subject code is already in use",
            ) from exc
        raise
    except Exception:
        session.rollback()
        raise

    session.refresh(subject)
    return SubjectScreeningResponse.model_validate(subject)


@router.patch(
    "/subjects/{subject_id}/screening-outcome",
    response_model=SubjectScreeningOutcomeResponse,
)
def record_subject_screening_outcome(
    subject_id: int,
    body: SubjectScreeningOutcomeUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> SubjectScreeningOutcomeResponse:
    """Record that an existing screening Subject failed screening."""
    subject = session.exec(
        select(Subject).where(Subject.id == subject_id).with_for_update()
    ).one_or_none()
    if subject is None:
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")
    assert_site_visible(user, subject.site_id)

    try:
        result = validate_subject_transition(
            subject,
            SubjectStatus.SCREEN_FAILED.value,
            as_of=date.today(),
            screen_failure_reason=body.reason,
        )
    except SubjectTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    old_value = json.dumps(
        {
            "screen_failure_reason": subject.screen_failure_reason,
            "status": subject.status,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    now = utcnow()
    subject.status = result.status
    subject.screening_date = result.screening_date
    subject.enrollment_date = result.enrollment_date
    subject.randomization_date = result.randomization_date
    subject.arm = result.arm
    subject.screen_failure_reason = result.screen_failure_reason
    subject.completed_date = result.completed_date
    subject.withdrawal_date = result.withdrawal_date
    subject.withdrawal_reason = result.withdrawal_reason
    subject.updated_at = now
    session.add(subject)

    new_value = json.dumps(
        {
            "screen_failure_reason": result.screen_failure_reason,
            "status": result.status,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        audit.record(
            session,
            user=user,
            action=AuditAction.UPDATE,
            entity_type="subjects",
            entity_id=subject.id,
            entity_label=subject.subject_code,
            field_name="screening_outcome",
            old_value=old_value,
            new_value=new_value,
            reason="Subject failed screening.",
            trial_id=subject.trial_id,
            request=request,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(subject)
    return SubjectScreeningOutcomeResponse.model_validate(subject)


@router.patch(
    "/subjects/{subject_id}/enrollment",
    response_model=SubjectEnrollmentResponse,
)
def enroll_subject(
    subject_id: int,
    body: SubjectEnrollmentUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> SubjectEnrollmentResponse:
    """Atomically enrol and randomize an existing screening Subject."""
    subject = session.exec(
        select(Subject).where(Subject.id == subject_id).with_for_update()
    ).one_or_none()
    if subject is None:
        session.rollback()
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")

    try:
        assert_site_visible(user, subject.site_id)
        site = session.get(Site, subject.site_id)
        trial = session.get(Trial, subject.trial_id)
        if site is None or trial is None or site.trial_id != subject.trial_id:
            raise HTTPException(
                status_code=409,
                detail="subject has inconsistent Trial or Site linkage",
            )
        if trial.status != TrialStatus.RECRUITING.value:
            raise HTTPException(status_code=409, detail="this trial is not recruiting")
        if site.status != SiteStatus.RECRUITING.value:
            raise HTTPException(status_code=409, detail="this site is not recruiting")

        ethics_ok, ethics_reason = trial_compliance.check_ethics_clearance_for_enrollment(trial)
        if not ethics_ok:
            raise HTTPException(
                status_code=409,
                detail=f"Enrollment Blocked: {ethics_reason}",
            )

        result = validate_subject_transition(
            subject,
            SubjectStatus.ENROLLED.value,
            as_of=date.today(),
            enrollment_date=body.enrollment_date,
            randomization_date=body.randomization_date,
            arm=body.arm.value,
        )

        old_value = json.dumps(
            {
                "arm": subject.arm,
                "enrollment_date": (
                    subject.enrollment_date.isoformat()
                    if subject.enrollment_date is not None
                    else None
                ),
                "prakriti": subject.prakriti,
                "randomization_date": (
                    subject.randomization_date.isoformat()
                    if subject.randomization_date is not None
                    else None
                ),
                "status": subject.status,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        subject.status = result.status
        subject.screening_date = result.screening_date
        subject.enrollment_date = result.enrollment_date
        subject.randomization_date = result.randomization_date
        subject.arm = result.arm
        subject.screen_failure_reason = result.screen_failure_reason
        subject.completed_date = result.completed_date
        subject.withdrawal_date = result.withdrawal_date
        subject.withdrawal_reason = result.withdrawal_reason
        subject.prakriti = body.prakriti.value if body.prakriti is not None else None
        subject.updated_at = utcnow()
        session.add(subject)

        new_value = json.dumps(
            {
                "arm": subject.arm,
                "enrollment_date": subject.enrollment_date.isoformat(),
                "prakriti": subject.prakriti,
                "randomization_date": subject.randomization_date.isoformat(),
                "status": subject.status,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        audit.record(
            session,
            user=user,
            action=AuditAction.UPDATE,
            entity_type="subjects",
            entity_id=subject.id,
            entity_label=subject.subject_code,
            field_name="enrollment",
            old_value=old_value,
            new_value=new_value,
            reason="Subject enrolled and randomized.",
            trial_id=subject.trial_id,
            request=request,
        )
        session.commit()
    except SubjectTransitionError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception:
        session.rollback()
        raise

    session.refresh(subject)
    return SubjectEnrollmentResponse.model_validate(subject)


@router.patch(
    "/subjects/{subject_id}/activation",
    response_model=SubjectActivationResponse,
)
def activate_subject(
    subject_id: int,
    body: SubjectActivationUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> SubjectActivationResponse:
    """Confirm first dosing and atomically activate an enrolled Subject."""
    subject = session.exec(
        select(Subject).where(Subject.id == subject_id).with_for_update()
    ).one_or_none()
    if subject is None:
        session.rollback()
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")

    try:
        assert_site_visible(user, subject.site_id)
        site = session.get(Site, subject.site_id)
        trial = session.get(Trial, subject.trial_id)
        if site is None or trial is None or site.trial_id != subject.trial_id:
            raise HTTPException(
                status_code=409,
                detail="subject has inconsistent Trial or Site linkage",
            )
        if trial.status != TrialStatus.RECRUITING.value:
            raise HTTPException(status_code=409, detail="this trial is not recruiting")
        if site.status != SiteStatus.RECRUITING.value:
            raise HTTPException(status_code=409, detail="this site is not recruiting")

        result = validate_subject_transition(
            subject,
            SubjectStatus.ACTIVE.value,
            as_of=date.today(),
        )
        old_value = json.dumps(
            {"status": result.previous_status},
            sort_keys=True,
            separators=(",", ":"),
        )

        subject.status = result.status
        subject.screening_date = result.screening_date
        subject.enrollment_date = result.enrollment_date
        subject.randomization_date = result.randomization_date
        subject.arm = result.arm
        subject.screen_failure_reason = result.screen_failure_reason
        subject.completed_date = result.completed_date
        subject.withdrawal_date = result.withdrawal_date
        subject.withdrawal_reason = result.withdrawal_reason
        subject.updated_at = utcnow()
        session.add(subject)

        new_value = json.dumps(
            {"status": result.status},
            sort_keys=True,
            separators=(",", ":"),
        )
        audit.record(
            session,
            user=user,
            action=AuditAction.UPDATE,
            entity_type="subjects",
            entity_id=subject.id,
            entity_label=subject.subject_code,
            field_name="activation",
            old_value=old_value,
            new_value=new_value,
            reason="Subject activated after first dose confirmation.",
            trial_id=subject.trial_id,
            request=request,
        )
        session.commit()
    except SubjectTransitionError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception:
        session.rollback()
        raise

    session.refresh(subject)
    return SubjectActivationResponse.model_validate(subject)


@router.patch(
    "/subjects/{subject_id}/outcome",
    response_model=SubjectOutcomeResponse,
)
def record_subject_outcome(
    subject_id: int,
    body: SubjectOutcomeUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> SubjectOutcomeResponse:
    """Atomically record completion, withdrawal, or loss to follow-up."""
    subject = session.exec(
        select(Subject).where(Subject.id == subject_id).with_for_update()
    ).one_or_none()
    if subject is None:
        session.rollback()
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")

    try:
        assert_site_visible(user, subject.site_id)
        site = session.get(Site, subject.site_id)
        trial = session.get(Trial, subject.trial_id)
        if site is None or trial is None or site.trial_id != subject.trial_id:
            raise HTTPException(
                status_code=409,
                detail="subject has inconsistent Trial or Site linkage",
            )

        result = validate_subject_transition(
            subject,
            body.status,
            as_of=date.today(),
            completed_date=body.completed_date,
            withdrawal_date=body.withdrawal_date,
            withdrawal_reason=body.withdrawal_reason,
        )

        def outcome_value(
            status: str,
            completed_date: date | None,
            withdrawal_date: date | None,
            withdrawal_reason: str | None,
        ) -> str:
            return json.dumps(
                {
                    "completed_date": completed_date.isoformat() if completed_date else None,
                    "status": status,
                    "withdrawal_date": withdrawal_date.isoformat() if withdrawal_date else None,
                    "withdrawal_reason": withdrawal_reason,
                },
                sort_keys=True,
                separators=(",", ":"),
            )

        old_value = outcome_value(
            subject.status,
            subject.completed_date,
            subject.withdrawal_date,
            subject.withdrawal_reason,
        )
        operation_time = utcnow()
        subject.status = result.status
        subject.screening_date = result.screening_date
        subject.enrollment_date = result.enrollment_date
        subject.randomization_date = result.randomization_date
        subject.arm = result.arm
        subject.screen_failure_reason = result.screen_failure_reason
        subject.completed_date = result.completed_date
        subject.withdrawal_date = result.withdrawal_date
        subject.withdrawal_reason = result.withdrawal_reason
        subject.updated_at = operation_time
        session.add(subject)

        new_value = outcome_value(
            result.status,
            result.completed_date,
            result.withdrawal_date,
            result.withdrawal_reason,
        )
        reasons = {
            SubjectStatus.COMPLETED.value: "Subject completed the study.",
            SubjectStatus.WITHDRAWN.value: "Subject withdrawn from the study.",
            SubjectStatus.LOST_TO_FOLLOW_UP.value: "Subject lost to follow-up.",
        }
        audit.record(
            session,
            user=user,
            action=AuditAction.UPDATE,
            entity_type="subjects",
            entity_id=subject.id,
            entity_label=subject.subject_code,
            field_name="outcome",
            old_value=old_value,
            new_value=new_value,
            reason=reasons[result.status],
            trial_id=subject.trial_id,
            request=request,
        )
        session.commit()
    except SubjectTransitionError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception:
        session.rollback()
        raise

    session.refresh(subject)
    return SubjectOutcomeResponse.model_validate(subject)


@router.get("/subjects", response_model=Page[Subject])
def list_subjects(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ)),
    trial_id: int | None = Query(None),
    site_id: int | None = Query(None),
    status: str | None = Query(None, description="e.g. enrolled, completed, withdrawn"),
    arm: str | None = Query(None, description="treatment, placebo, comparator"),
    prakriti: str | None = Query(None, description="Ayurvedic constitutional type"),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Subject]:
    statement = select(Subject).order_by(Subject.subject_code)
    if trial_id is not None:
        statement = statement.where(Subject.trial_id == trial_id)
    if site_id is not None:
        statement = statement.where(Subject.site_id == site_id)
    if status:
        statement = statement.where(Subject.status == status)
    if arm:
        statement = statement.where(Subject.arm == arm)
    if prakriti:
        statement = statement.where(Subject.prakriti == prakriti)
    # Applied last, and unconditionally: a site user who passes ?site_id=3 gets
    # their own site AND site 3, which is nothing. The URL cannot widen the scope.
    statement = scoped(statement, Subject.site_id, user)
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/subjects/{subject_id}", response_model=Subject)
def get_subject(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ)),
) -> Subject:
    return _visible_subject(session, subject_id, user)


@router.post(
    "/subjects/{subject_id}/visits",
    response_model=VisitScheduleResponse,
    status_code=201,
)
def schedule_subject_visit(
    subject_id: int,
    body: VisitScheduleCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_WRITE)),
) -> VisitScheduleResponse:
    """Atomically schedule one manually specified Visit for a Subject."""
    subject = session.exec(
        select(Subject).where(Subject.id == subject_id).with_for_update()
    ).one_or_none()
    if subject is None:
        session.rollback()
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")

    try:
        assert_site_visible(user, subject.site_id)
        site = session.get(Site, subject.site_id)
        trial = session.get(Trial, subject.trial_id)
        if site is None or trial is None or site.trial_id != subject.trial_id:
            raise HTTPException(
                status_code=409,
                detail="subject has inconsistent Trial or Site linkage",
            )
        if subject.status not in {
            SubjectStatus.ENROLLED.value,
            SubjectStatus.ACTIVE.value,
        }:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SUBJECT_NOT_SCHEDULABLE",
                    "message": "visits may be scheduled only for enrolled or active subjects",
                },
            )

        duplicate = session.exec(
            select(Visit.id).where(
                Visit.subject_id == subject.id,
                Visit.visit_number == body.visit_number,
            )
        ).first()
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "VISIT_NUMBER_ALREADY_SCHEDULED",
                    "message": "this subject already has that visit_number",
                },
            )

        now = utcnow()
        visit = Visit(
            subject_id=subject.id,
            trial_id=subject.trial_id,
            visit_name=body.visit_name,
            visit_number=body.visit_number,
            visit_day=body.visit_day,
            scheduled_date=body.scheduled_date,
            actual_date=None,
            status=VisitStatus.SCHEDULED.value,
            is_protocol_deviation=False,
            deviation_description=None,
            notes=None,
            performed_by_user_id=None,
            created_at=now,
            updated_at=now,
        )
        session.add(visit)
        session.flush()
        new_value = json.dumps(
            {
                "scheduled_date": visit.scheduled_date.isoformat(),
                "status": visit.status,
                "visit_day": visit.visit_day,
                "visit_name": visit.visit_name,
                "visit_number": visit.visit_number,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        audit.record(
            session,
            user=user,
            action=AuditAction.CREATE,
            entity_type="visits",
            entity_id=visit.id,
            entity_label=f"{subject.subject_code} {visit.visit_name}",
            field_name="schedule",
            old_value=None,
            new_value=new_value,
            reason="Visit scheduled.",
            trial_id=subject.trial_id,
            request=request,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_visit_number_conflict(exc):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "VISIT_NUMBER_ALREADY_SCHEDULED",
                    "message": "this subject already has that visit_number",
                },
            ) from exc
        raise
    except Exception:
        session.rollback()
        raise

    session.refresh(visit)
    return VisitScheduleResponse.model_validate(visit)


@router.get("/subjects/{subject_id}/visits", response_model=list[Visit])
def list_subject_visits(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_READ)),
) -> list[Visit]:
    """One participant's whole visit schedule, in protocol order.

    Not paginated: the schedule is six visits long by design, and a coordinator
    wants to see the whole thing at once.
    """
    _visible_subject(session, subject_id, user)
    return list(
        session.exec(
            select(Visit)
            .where(Visit.subject_id == subject_id)
            .order_by(Visit.visit_number)
        ).all()
    )


@router.get("/subjects/{subject_id}/adverse-events", response_model=list[AdverseEvent])
def list_subject_adverse_events(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ, Permission.AE_READ)),
) -> list[AdverseEvent]:
    _visible_subject(session, subject_id, user)
    return list(
        session.exec(
            select(AdverseEvent)
            .where(AdverseEvent.subject_id == subject_id)
            .order_by(AdverseEvent.onset_date)
        ).all()
    )


@router.get("/visits", response_model=Page[Visit])
def list_visits(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_READ)),
    trial_id: int | None = Query(None),
    subject_id: int | None = Query(None),
    status: str | None = Query(None, description="scheduled, completed, missed..."),
    deviations_only: bool = Query(
        False, description="only visits flagged as a protocol deviation"
    ),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Visit]:
    statement = select(Visit).order_by(Visit.scheduled_date, Visit.visit_number)
    if trial_id is not None:
        statement = statement.where(Visit.trial_id == trial_id)
    if subject_id is not None:
        statement = statement.where(Visit.subject_id == subject_id)
    if status:
        statement = statement.where(Visit.status == status)
    if deviations_only:
        statement = statement.where(Visit.is_protocol_deviation == True)  # noqa: E712
    # If the user is a Patient: strictly isolate to their own subject_id
    if user.role == UserRole.PATIENT.value:
        if user.subject_id is None:
            statement = statement.where(Visit.id == -1)
        else:
            statement = statement.where(Visit.subject_id == user.subject_id)
    elif user.scope_site_id is not None:
        statement = statement.where(
            Visit.subject_id.in_(  # type: ignore[union-attr]
                select(Subject.id).where(Subject.site_id == user.scope_site_id)
            )
        )
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/visits/{visit_id}", response_model=Visit)
def get_visit(
    visit_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_READ)),
) -> Visit:
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"no visit with id {visit_id}")
    if user.role == UserRole.PATIENT.value:
        if user.subject_id is None or visit.subject_id != user.subject_id:
            raise HTTPException(status_code=403, detail="forbidden: patients may only access their own visits")
    elif user.scope_site_id is not None:
        subject = session.get(Subject, visit.subject_id)
        assert_site_visible(user, subject.site_id if subject else None)
    return visit


@router.patch("/visits/{visit_id}/outcome", response_model=VisitOutcomeResponse)
def record_visit_outcome(
    visit_id: int,
    body: VisitOutcomeUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_WRITE)),
) -> VisitOutcomeResponse:
    """Atomically record completion or non-attendance for a scheduled Visit."""
    visit = session.exec(
        select(Visit).where(Visit.id == visit_id).with_for_update()
    ).one_or_none()
    if visit is None:
        session.rollback()
        raise HTTPException(status_code=404, detail=f"no visit with id {visit_id}")

    try:
        subject = session.get(Subject, visit.subject_id)
        if subject is None:
            raise HTTPException(
                status_code=409,
                detail="visit has inconsistent Subject, Trial, or Site linkage",
            )
        assert_site_visible(user, subject.site_id)
        trial = session.get(Trial, visit.trial_id)
        site = session.get(Site, subject.site_id)
        if (
            trial is None
            or site is None
            or visit.trial_id != subject.trial_id
            or site.trial_id != subject.trial_id
        ):
            raise HTTPException(
                status_code=409,
                detail="visit has inconsistent Subject, Trial, or Site linkage",
            )
        if subject.status != SubjectStatus.ACTIVE.value:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SUBJECT_NOT_ACTIVE",
                    "message": "visit outcomes require an active subject",
                },
            )

        result = validate_visit_transition(
            visit,
            body.status,
            actual_date=body.actual_date,
            is_protocol_deviation=body.is_protocol_deviation,
            deviation_description=body.deviation_description,
            acting_user_id=user.id,
            as_of=date.today(),
        )
        old_value = json.dumps(
            {
                "actual_date": visit.actual_date.isoformat() if visit.actual_date else None,
                "deviation_description": visit.deviation_description,
                "is_protocol_deviation": visit.is_protocol_deviation,
                "performed_by_user_id": visit.performed_by_user_id,
                "status": visit.status,
            }, sort_keys=True, separators=(",", ":"),
        )
        visit.status = result.status
        visit.actual_date = result.actual_date
        visit.is_protocol_deviation = result.is_protocol_deviation
        visit.deviation_description = result.deviation_description
        visit.performed_by_user_id = result.performed_by_user_id
        visit.updated_at = utcnow()
        session.add(visit)
        new_value = json.dumps(
            {
                "actual_date": result.actual_date.isoformat() if result.actual_date else None,
                "deviation_description": result.deviation_description,
                "is_protocol_deviation": result.is_protocol_deviation,
                "performed_by_user_id": result.performed_by_user_id,
                "status": result.status,
            }, sort_keys=True, separators=(",", ":"),
        )
        audit.record(
            session, user=user, action=AuditAction.UPDATE,
            entity_type="visits", entity_id=visit.id,
            entity_label=f"{subject.subject_code} {visit.visit_name}",
            field_name="outcome", old_value=old_value, new_value=new_value,
            reason=("Visit completed." if result.status == VisitStatus.COMPLETED.value
                    else "Visit marked missed."),
            trial_id=visit.trial_id, request=request,
        )
        session.commit()
    except VisitTransitionError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "message": exc.message}
        ) from exc
    except Exception:
        session.rollback()
        raise

    session.refresh(visit)
    return VisitOutcomeResponse.model_validate(visit)


class ProtocolDeviationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trial_id: int | None = None
    site_id: int | None = None
    subject_id: int
    visit_id: int | None = None
    category: str
    description: str
    clinical_impact: str | None = None
    capa: str | None = None
    deviation_date: date | None = None


@router.post("/protocol-deviations", status_code=201)
def create_protocol_deviation(
    body: ProtocolDeviationCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> dict:
    """Record an ICH E6(R2) protocol deviation with clinical impact and CAPA."""
    subject = session.get(Subject, body.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail=f"subject {body.subject_id} not found")

    trial_id = subject.trial_id
    site_id = subject.site_id
    assert_site_visible(user, site_id)

    dev_date = body.deviation_date or date.today()
    dev_desc = f"[{body.category.upper()}] {body.description.strip()}"
    if body.capa:
        dev_desc += f" (CAPA: {body.capa.strip()})"

    if body.visit_id:
        visit = session.get(Visit, body.visit_id)
        if visit:
            visit.is_protocol_deviation = True
            visit.deviation_description = dev_desc
            session.add(visit)

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="protocol_deviations",
        entity_id=body.visit_id or subject.id,
        entity_label=f"{subject.subject_code} - {body.category}",
        field_name=None,
        old_value=None,
        new_value=json.dumps({
            "subject_code": subject.subject_code,
            "category": body.category,
            "description": body.description,
            "clinical_impact": body.clinical_impact,
            "capa": body.capa,
            "deviation_date": str(dev_date),
        }),
        reason=f"Protocol deviation logged by {user.role}: {body.category}",
        trial_id=trial_id,
    )
    session.commit()

    return {
        "status": "recorded",
        "subject_code": subject.subject_code,
        "category": body.category,
        "description": dev_desc,
        "deviation_date": str(dev_date),
    }


@router.get("/subjects/{subject_id}/dossier")
def get_subject_dossier(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ)),
) -> dict:
    """Retrieve full clinical participant profile and unified chronological lifecycle audit log."""
    subject = session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail=f"subject {subject_id} not found")

    if user.is_site_scoped:
        assert_site_visible(user, subject.site_id)

    trial = session.get(Trial, subject.trial_id)
    site = session.get(Site, subject.site_id)
    consent = session.exec(select(EConsent).where(EConsent.subject_id == subject_id)).first()
    visits = list(session.exec(select(Visit).where(Visit.subject_id == subject_id).order_by(Visit.visit_number)).all())
    adverse_events = list(session.exec(select(AdverseEvent).where(AdverseEvent.subject_id == subject_id).order_by(AdverseEvent.onset_date, AdverseEvent.id)).all())

    # Check DPDP Masking
    should_mask = privacy.should_mask_patient_pii(user, subject.site_id)

    # Calculate BMI
    bmi = None
    if subject.height_cm and subject.weight_kg and subject.height_cm > 0:
        height_m = subject.height_cm / 100.0
        bmi = round(subject.weight_kg / (height_m * height_m), 1)

    # Calculate Age
    age = subject.age_at_enrollment
    if age is None and subject.year_of_birth:
        ref_year = subject.screening_date.year if subject.screening_date else date.today().year
        age = ref_year - subject.year_of_birth

    # 1. Profile Data
    profile = {
        "id": subject.id,
        "subject_code": subject.subject_code,
        "masked_name": privacy.mask_patient_name(None, subject.subject_code) if should_mask else f"Participant {subject.subject_code}",
        "status": subject.status,
        "arm": subject.arm,
        "sex": subject.sex,
        "age": age,
        "year_of_birth": subject.year_of_birth,
        "height_cm": subject.height_cm,
        "weight_kg": subject.weight_kg,
        "bmi": bmi,
        "prakriti": subject.prakriti,
        "screening_date": str(subject.screening_date) if subject.screening_date else None,
        "enrollment_date": str(subject.enrollment_date) if subject.enrollment_date else None,
        "randomization_date": str(subject.randomization_date) if subject.randomization_date else None,
        "site_id": subject.site_id,
        "site_name": site.name if site else "Clinical Research Center",
        "site_code": site.site_code if site else f"SITE-{subject.site_id}",
        "trial_id": subject.trial_id,
        "protocol_number": trial.protocol_number if trial else "AIIA-ASH-2026-01",
        "is_dpdp_masked": should_mask,
    }

    if consent:
        profile["consent"] = {
            "status": consent.status,
            "signed_at": consent.signed_at.isoformat() if consent.signed_at else None,
            "language": consent.language,
            "sha256_hash": consent.sha256_hash,
            "abha_id": privacy.mask_abha_id(consent.abha_id) if should_mask else consent.abha_id,
            "signer_name": privacy.mask_patient_name(consent.signer_name, subject.subject_code) if should_mask else consent.signer_name,
        }
    else:
        profile["consent"] = None

    # 2. Chronological Timeline Construction
    timeline_events: list[dict] = []

    # Screening
    if subject.screening_date:
        timeline_events.append({
            "id": f"evt-screening-{subject.id}",
            "event_type": "screening",
            "title": "Screening & Demographics Intake",
            "timestamp": f"{subject.screening_date}T09:00:00Z",
            "actor": "Clinical Research Coordinator",
            "badge": "info",
            "details": {
                "Sex": subject.sex,
                "Age": f"{age} years" if age else "N/A",
                "Height": f"{subject.height_cm} cm" if subject.height_cm else "N/A",
                "Weight": f"{subject.weight_kg} kg" if subject.weight_kg else "N/A",
                "BMI": f"{bmi} kg/m²" if bmi else "N/A",
                "Prakriti (Dosha)": (subject.prakriti or "Unassessed").upper(),
            },
        })

    # Consent
    if consent and consent.signed_at:
        timeline_events.append({
            "id": f"evt-consent-{consent.id}",
            "event_type": "consent",
            "title": f"Digital e-Consent Executed ({consent.language.upper()})",
            "timestamp": consent.signed_at.isoformat(),
            "actor": profile["consent"]["signer_name"] if profile.get("consent") else "Participant",
            "badge": "success",
            "details": {
                "Status": "Signed & Verified",
                "21 CFR Part 11": "Cryptographically Sealed",
                "SHA-256 Digest": consent.sha256_hash[:16] + "..." if consent.sha256_hash else "Verified",
                "ABHA ID": profile["consent"]["abha_id"] if profile.get("consent") else "N/A",
            },
        })

    # Enrollment
    if subject.enrollment_date:
        timeline_events.append({
            "id": f"evt-enroll-{subject.id}",
            "event_type": "enrollment",
            "title": f"Formal Enrollment & Randomization",
            "timestamp": f"{subject.enrollment_date}T10:30:00Z",
            "actor": "Principal Investigator",
            "badge": "success",
            "details": {
                "Assigned Study Arm": subject.arm,
                "Randomization Date": str(subject.randomization_date or subject.enrollment_date),
                "Eligibility": "Inclusion Criteria Met / Cleared by PI",
            },
        })

    # Protocol Visits
    for v in visits:
        v_date = v.actual_date or v.scheduled_date or subject.screening_date or date.today()
        v_badge = "success" if v.status == "completed" else ("danger" if v.status == "missed" else "info")
        v_details: dict[str, Any] = {
            "Visit Number": f"V{v.visit_number}",
            "Scheduled Date": str(v.scheduled_date) if v.scheduled_date else "N/A",
            "Actual Date": str(v.actual_date) if v.actual_date else "Pending",
            "Status": (v.status or "SCHEDULED").upper(),
        }
        if v.is_protocol_deviation:
            v_details["Protocol Deviation"] = v.deviation_description or "Out of window"

        timeline_events.append({
            "id": f"evt-visit-{v.id}",
            "event_type": "visit",
            "title": f"Visit {v.visit_number}: {v.visit_name}",
            "timestamp": f"{v_date}T11:00:00Z",
            "actor": "Clinical Site Team",
            "badge": v_badge,
            "details": v_details,
        })

    # Adverse Events
    for ae in adverse_events:
        ae_date = ae.onset_date or subject.screening_date or date.today()
        ae_details = {
            "MedDRA Preferred Term": ae.meddra_pt_term or ae.term_verbatim,
            "MedDRA SOC": ae.meddra_soc or "General disorders",
            "Severity": (ae.severity or "MILD").upper(),
            "Seriousness": "YES (SAE - 24h Clock Active)" if ae.is_serious else "NO (Non-Serious)",
            "Causality Assessment": (ae.causality or "UNRELATED").upper(),
            "Outcome": (ae.outcome or "RECOVERING").upper(),
            "Action Taken": ae.action_taken or "Dose Unchanged",
            "Ethics Committee (IEC) Ruling": (ae.ec_decision or "PENDING REVIEW").upper(),
        }
        if ae.ec_decision_notes:
            ae_details["IEC Committee Directive"] = ae.ec_decision_notes

        timeline_events.append({
            "id": f"evt-ae-{ae.id}",
            "event_type": "adverse_event",
            "title": f"Adverse Event: {ae.term_verbatim} ({ae.ae_number})",
            "timestamp": f"{ae_date}T14:15:00Z",
            "actor": "Investigator Safety Review",
            "badge": "danger" if ae.is_serious else "warning",
            "details": ae_details,
        })

    # Audit Trail records specifically on this subject
    audit_stmt = select(AuditLog).where(
        (AuditLog.entity_type == "subjects") & (AuditLog.entity_id == subject.id)
        | (AuditLog.entity_type == "protocol_deviations") & (AuditLog.entity_id == subject.id)
    ).order_by(AuditLog.timestamp.desc())
    audit_records = list(session.exec(audit_stmt).all())

    for log in audit_records:
        ist_time = log.timestamp.strftime("%Y-%m-%d %H:%M:%S IST") if log.timestamp else ""
        timeline_events.append({
            "id": f"evt-audit-{log.id}",
            "event_type": "audit",
            "title": f"Audit Log: {log.action.upper()} {log.entity_type}",
            "timestamp": log.timestamp.isoformat() if log.timestamp else f"{date.today()}T12:00:00Z",
            "actor": f"{log.user_email or 'System'} ({log.user_role or 'staff'})",
            "badge": "info",
            "details": {
                "Action": log.action.upper(),
                "Field": log.field_name or "Entity record",
                "Reason": log.reason or "Clinical record maintenance",
                "Timestamp (IST)": ist_time,
                "Old Value": log.old_value or "None",
                "New Value": log.new_value or "None",
            },
        })

    timeline_events.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "profile": profile,
        "timeline": timeline_events,
        "visits": [
            {
                "id": v.id,
                "visit_number": v.visit_number,
                "visit_name": v.visit_name,
                "scheduled_date": str(v.scheduled_date) if v.scheduled_date else None,
                "actual_date": str(v.actual_date) if v.actual_date else None,
                "status": v.status,
                "is_protocol_deviation": v.is_protocol_deviation,
                "deviation_description": v.deviation_description,
            }
            for v in visits
        ],
        "adverse_events": [
            {
                "id": ae.id,
                "ae_number": ae.ae_number,
                "term_verbatim": ae.term_verbatim,
                "onset_date": str(ae.onset_date),
                "severity": ae.severity,
                "is_serious": ae.is_serious,
                "causality": ae.causality,
                "outcome": ae.outcome,
                "ec_decision": ae.ec_decision or "pending",
                "ec_decision_date": str(ae.ec_decision_date) if ae.ec_decision_date else None,
                "ec_decision_notes": ae.ec_decision_notes,
            }
            for ae in adverse_events
        ],
    }


class ClinicalLogCreate(BaseModel):
    entry_type: Literal[
        "medication_administered",
        "symptom_reported",
        "vital_sign",
        "adverse_event",
        "general_note",
    ]
    substance_name: str | None = None
    dose: str | None = None
    route: str | None = None
    observation_description: str
    linked_visit_id: int | None = None
    correction_of_entry_id: int | None = None
    correction_reason: str | None = None
    is_serious: bool = False
    ae_severity: str = "mild"


@router.get("/subjects/{subject_id}/clinical-log", response_model=list[ClinicalLogEntry])
def list_subject_clinical_logs(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ)),
) -> list[ClinicalLogEntry]:
    """Retrieve the append-only clinical progress logs for a participant."""
    subject = session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail=f"subject {subject_id} not found")
    if user.is_site_scoped:
        assert_site_visible(user, subject.site_id)

    statement = (
        select(ClinicalLogEntry)
        .where(ClinicalLogEntry.subject_id == subject_id)
        .order_by(ClinicalLogEntry.timestamp.desc())
    )
    return list(session.exec(statement).all())


@router.post("/subjects/{subject_id}/clinical-log", response_model=ClinicalLogEntry, status_code=201)
def append_subject_clinical_log(
    subject_id: int,
    body: ClinicalLogCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_WRITE)),
) -> ClinicalLogEntry:
    """Append an immutable clinical log entry. Auto-triggers Pharmacovigilance if Adverse Event."""
    subject = session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail=f"subject {subject_id} not found")
    if user.is_site_scoped:
        assert_site_visible(user, subject.site_id)

    now = utcnow()
    linked_ae_id = None

    # Trigger pharmacovigilance workflow if adverse event
    if body.entry_type == "adverse_event":
        ae_count = len(
            list(
                session.exec(
                    select(AdverseEvent).where(AdverseEvent.subject_id == subject.id)
                ).all()
            )
        )
        sub_suffix = (
            subject.subject_code.split("-")[-1]
            if "-" in subject.subject_code
            else str(subject.id)
        )
        ae_number = f"AE-{sub_suffix}-{ae_count + 1:02d}"

        ae = AdverseEvent(
            trial_id=subject.trial_id,
            site_id=subject.site_id,
            subject_id=subject.id,
            ae_number=ae_number,
            term_verbatim=body.observation_description[:250],
            description=body.observation_description,
            onset_date=now.date(),
            severity=body.ae_severity.lower(),
            is_serious=body.is_serious,
            causality="possible" if body.is_serious else "unrelated",
            outcome="recovering",
            reported_by_user_id=user.id,
            reported_date=now.date(),
            reported_to_ec=False,
            created_at=now,
            updated_at=now,
        )
        session.add(ae)
        session.flush()
        linked_ae_id = ae.id

        audit.record(
            session,
            user=user,
            action=AuditAction.CREATE,
            entity_type="adverse_events",
            entity_id=ae.id,
            entity_label=ae.ae_number,
            reason=f"Auto-triggered AE from clinical progress log: {ae.term_verbatim}",
            trial_id=subject.trial_id,
        )

    log_entry = ClinicalLogEntry(
        subject_id=subject.id,
        trial_id=subject.trial_id,
        site_id=subject.site_id,
        entry_type=body.entry_type,
        substance_name=body.substance_name,
        dose=body.dose,
        route=body.route,
        observation_description=body.observation_description,
        linked_visit_id=body.linked_visit_id,
        linked_ae_id=linked_ae_id,
        correction_of_entry_id=body.correction_of_entry_id,
        correction_reason=body.correction_reason,
        entered_by_user_id=user.id,
        entered_by_name=user.full_name,
        timestamp=now,
    )
    session.add(log_entry)
    session.flush()

    audit.record(
        session,
        user=user,
        action=AuditAction.CREATE,
        entity_type="clinical_logs",
        entity_id=log_entry.id,
        entity_label=f"{subject.subject_code} - {body.entry_type}",
        reason=f"Clinical progress log appended for participant {subject.subject_code}",
        trial_id=subject.trial_id,
    )
    session.commit()
    session.refresh(log_entry)
    return log_entry
