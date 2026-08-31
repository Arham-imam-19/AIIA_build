"""Pure validation for transitions of an existing trial subject."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.enums import StudyArm, SubjectStatus
from app.models.subject import Subject


class SubjectTransitionError(ValueError):
    """A requested subject transition violates the lifecycle policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SubjectTransitionResult:
    """Validated lifecycle values for the caller to persist atomically."""

    previous_status: str
    status: str
    screening_date: date | None
    enrollment_date: date | None
    randomization_date: date | None
    arm: str
    screen_failure_reason: str | None
    completed_date: date | None
    withdrawal_date: date | None
    withdrawal_reason: str | None


_ALLOWED_TRANSITIONS = frozenset(
    {
        (SubjectStatus.SCREENING.value, SubjectStatus.SCREEN_FAILED.value),
        (SubjectStatus.SCREENING.value, SubjectStatus.ENROLLED.value),
        (SubjectStatus.ENROLLED.value, SubjectStatus.ACTIVE.value),
        (SubjectStatus.ENROLLED.value, SubjectStatus.WITHDRAWN.value),
        (SubjectStatus.ENROLLED.value, SubjectStatus.LOST_TO_FOLLOW_UP.value),
        (SubjectStatus.ACTIVE.value, SubjectStatus.COMPLETED.value),
        (SubjectStatus.ACTIVE.value, SubjectStatus.WITHDRAWN.value),
        (SubjectStatus.ACTIVE.value, SubjectStatus.LOST_TO_FOLLOW_UP.value),
    }
)


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def _reject(code: str, message: str) -> None:
    raise SubjectTransitionError(code, message)


def validate_subject_transition(
    subject: Subject,
    target_status: str,
    *,
    as_of: date | None = None,
    screen_failure_reason: str | None = None,
    enrollment_date: date | None = None,
    randomization_date: date | None = None,
    arm: str | None = None,
    completed_date: date | None = None,
    withdrawal_date: date | None = None,
    withdrawal_reason: str | None = None,
) -> SubjectTransitionResult:
    """Validate one transition without reading or mutating persistence."""
    evaluation_date = as_of or date.today()
    transition = (subject.status, target_status)
    if transition not in _ALLOWED_TRANSITIONS:
        _reject(
            "TRANSITION_NOT_ALLOWED",
            f"Subject transition from '{subject.status}' to '{target_status}' is not allowed.",
        )

    if target_status == SubjectStatus.SCREEN_FAILED.value:
        if not _present(screen_failure_reason):
            _reject("SCREEN_FAILURE_REASON_REQUIRED", "A screen failure reason is required.")
        if subject.arm != StudyArm.NOT_RANDOMIZED.value or arm not in {
            None,
            StudyArm.NOT_RANDOMIZED.value,
        }:
            _reject("ARM_MUST_REMAIN_NOT_RANDOMIZED", "A screen failure cannot have a randomised arm.")
        if any(
            value is not None
            for value in (
                subject.enrollment_date,
                subject.randomization_date,
                enrollment_date,
                randomization_date,
            )
        ):
            _reject("ENROLLMENT_FIELDS_MUST_BE_EMPTY", "A screen failure cannot have enrolment or randomisation dates.")
        if (
            subject.completed_date is not None
            or subject.withdrawal_date is not None
            or subject.withdrawal_reason is not None
            or completed_date is not None
            or withdrawal_date is not None
            or withdrawal_reason is not None
        ):
            _reject("EXIT_FIELDS_MUST_BE_EMPTY", "A screen failure cannot have completion or withdrawal fields.")
        return SubjectTransitionResult(
            previous_status=subject.status,
            status=target_status,
            screening_date=subject.screening_date,
            enrollment_date=None,
            randomization_date=None,
            arm=subject.arm,
            screen_failure_reason=screen_failure_reason.strip(),
            completed_date=None,
            withdrawal_date=None,
            withdrawal_reason=None,
        )

    if target_status == SubjectStatus.ENROLLED.value:
        if enrollment_date is None or randomization_date is None:
            _reject("ENROLLMENT_DATES_REQUIRED", "Enrolment and randomisation dates are required.")
        if subject.screening_date is None:
            _reject("SCREENING_DATE_REQUIRED", "A screening date is required before enrolment.")
        if arm is None or arm == StudyArm.NOT_RANDOMIZED.value:
            _reject("RANDOMIZED_ARM_REQUIRED", "A randomised study arm is required.")
        randomized_arms = {
            StudyArm.TREATMENT.value,
            StudyArm.PLACEBO.value,
            StudyArm.COMPARATOR.value,
        }
        if arm not in randomized_arms:
            _reject("INVALID_RANDOMIZED_ARM", f"'{arm}' is not a randomised study arm.")
        if (
            subject.screen_failure_reason is not None
            or subject.completed_date is not None
            or subject.withdrawal_date is not None
            or subject.withdrawal_reason is not None
            or screen_failure_reason is not None
            or completed_date is not None
            or withdrawal_date is not None
            or withdrawal_reason is not None
        ):
            _reject("OUTCOME_FIELDS_MUST_BE_EMPTY", "Screen failure, completion, and withdrawal fields must be empty at enrolment.")
        if not subject.screening_date <= enrollment_date <= randomization_date:
            _reject("ENROLLMENT_DATES_OUT_OF_ORDER", "Screening, enrolment, and randomisation dates are out of order.")
        if any(day > evaluation_date for day in (subject.screening_date, enrollment_date, randomization_date)):
            _reject("FUTURE_SUBJECT_DATE", "Screening, enrolment, and randomisation dates cannot be in the future.")
        return SubjectTransitionResult(
            previous_status=subject.status,
            status=target_status,
            screening_date=subject.screening_date,
            enrollment_date=enrollment_date,
            randomization_date=randomization_date,
            arm=arm,
            screen_failure_reason=None,
            completed_date=None,
            withdrawal_date=None,
            withdrawal_reason=None,
        )

    if target_status == SubjectStatus.ACTIVE.value:
        if subject.enrollment_date is None or subject.randomization_date is None:
            _reject(
                "ENROLLMENT_FACTS_REQUIRED",
                "Enrolment and randomisation dates are required before activation.",
            )
        randomized_arms = {
            StudyArm.TREATMENT.value,
            StudyArm.PLACEBO.value,
            StudyArm.COMPARATOR.value,
        }
        if subject.arm not in randomized_arms:
            _reject(
                "RANDOMIZED_ARM_REQUIRED",
                "A valid randomised study arm is required before activation.",
            )
        if (
            subject.screen_failure_reason is not None
            or subject.completed_date is not None
            or subject.withdrawal_date is not None
            or subject.withdrawal_reason is not None
            or screen_failure_reason is not None
            or completed_date is not None
            or withdrawal_date is not None
            or withdrawal_reason is not None
        ):
            _reject(
                "OUTCOME_FIELDS_MUST_BE_EMPTY",
                "Screen failure, completion, and withdrawal fields must be empty at activation.",
            )
        return SubjectTransitionResult(
            previous_status=subject.status,
            status=target_status,
            screening_date=subject.screening_date,
            enrollment_date=subject.enrollment_date,
            randomization_date=subject.randomization_date,
            arm=subject.arm,
            screen_failure_reason=None,
            completed_date=None,
            withdrawal_date=None,
            withdrawal_reason=None,
        )

    if subject.enrollment_date is None:
        _reject("ENROLLMENT_DATE_REQUIRED", "An enrolment date is required before an exit.")
    if subject.screen_failure_reason is not None or screen_failure_reason is not None:
        _reject("SCREEN_FAILURE_REASON_MUST_BE_EMPTY", "An enrolled subject cannot retain a screen failure reason.")

    if target_status == SubjectStatus.COMPLETED.value:
        if completed_date is None:
            _reject("COMPLETION_DATE_REQUIRED", "A completion date is required.")
        if (
            subject.withdrawal_date is not None
            or subject.withdrawal_reason is not None
            or withdrawal_date is not None
            or withdrawal_reason is not None
        ):
            _reject("WITHDRAWAL_FIELDS_MUST_BE_EMPTY", "A completed subject cannot have withdrawal fields.")
        if completed_date < subject.enrollment_date:
            _reject("COMPLETION_BEFORE_ENROLLMENT", "Completion cannot precede enrolment.")
        if completed_date > evaluation_date:
            _reject("FUTURE_COMPLETION_DATE", "Completion cannot be in the future.")
        return SubjectTransitionResult(
            previous_status=subject.status,
            status=target_status,
            screening_date=subject.screening_date,
            enrollment_date=subject.enrollment_date,
            randomization_date=subject.randomization_date,
            arm=subject.arm,
            screen_failure_reason=None,
            completed_date=completed_date,
            withdrawal_date=None,
            withdrawal_reason=None,
        )

    if withdrawal_date is None or not _present(withdrawal_reason):
        _reject("WITHDRAWAL_DETAILS_REQUIRED", "A withdrawal date and reason are required.")
    if subject.completed_date is not None or completed_date is not None:
        _reject("COMPLETION_FIELD_MUST_BE_EMPTY", "A withdrawn subject cannot have a completion date.")
    if withdrawal_date < subject.enrollment_date:
        _reject("WITHDRAWAL_BEFORE_ENROLLMENT", "Withdrawal cannot precede enrolment.")
    if withdrawal_date > evaluation_date:
        _reject("FUTURE_WITHDRAWAL_DATE", "Withdrawal cannot be in the future.")
    return SubjectTransitionResult(
        previous_status=subject.status,
        status=target_status,
        screening_date=subject.screening_date,
        enrollment_date=subject.enrollment_date,
        randomization_date=subject.randomization_date,
        arm=subject.arm,
        screen_failure_reason=None,
        completed_date=None,
        withdrawal_date=withdrawal_date,
        withdrawal_reason=withdrawal_reason.strip(),
    )
