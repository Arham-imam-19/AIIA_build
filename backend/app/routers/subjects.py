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
    VisitStatus,
)
from app.models import AdverseEvent, Site, Subject, Trial, Visit
from app.models.base import utcnow
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate
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
    """Fetch a subject, 404 if absent and 403 if it belongs to another site."""
    subject = session.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")
    assert_site_visible(user, subject.site_id)
    return subject


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

    now = utcnow()
    code = _next_subject_code(session, site)
    subject = Subject(
        trial_id=trial.id,
        site_id=site.id,
        subject_code=code,
        status=SubjectStatus.SCREENING.value,
        screening_date=body.screening_date,
        enrollment_date=None,
        randomization_date=None,
        arm=StudyArm.NOT_RANDOMIZED.value,
        year_of_birth=body.year_of_birth,
        age_at_enrollment=None,
        sex=body.sex.value,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        prakriti=None,
        completed_date=None,
        withdrawal_date=None,
        withdrawal_reason=None,
        screen_failure_reason=None,
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
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ, Permission.VISIT_READ)),
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
    # A visit has no site column of its own - it inherits one from its subject.
    # So the scope is applied by joining through subjects.
    if user.scope_site_id is not None:
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
    if user.scope_site_id is not None:
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
