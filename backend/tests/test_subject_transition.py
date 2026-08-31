"""Unit tests for the pure Subject transition policy."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.enums import StudyArm, SubjectStatus
from app.models import Subject
from app.services.subject_transition import (
    SubjectTransitionError,
    validate_subject_transition,
)


AS_OF = date(2026, 8, 26)
SCREENED = date(2026, 8, 10)
ENROLLED = date(2026, 8, 20)


def subject(status: SubjectStatus, **overrides) -> Subject:
    values = {
        "trial_id": 1,
        "site_id": 1,
        "subject_code": "SYNTHETIC-P03-001",
        "status": status.value,
        "screening_date": SCREENED,
        "enrollment_date": None,
        "randomization_date": None,
        "arm": StudyArm.NOT_RANDOMIZED.value,
        "sex": "female",
        "screen_failure_reason": None,
        "completed_date": None,
        "withdrawal_date": None,
        "withdrawal_reason": None,
    }
    if status in {SubjectStatus.ENROLLED, SubjectStatus.ACTIVE}:
        values.update(
            enrollment_date=ENROLLED,
            randomization_date=ENROLLED,
            arm=StudyArm.TREATMENT.value,
        )
    values.update(overrides)
    return Subject(**values)


def request(current: SubjectStatus, target: SubjectStatus, **overrides):
    kwargs = {"as_of": AS_OF}
    if target == SubjectStatus.SCREEN_FAILED:
        kwargs["screen_failure_reason"] = "Eligibility criterion not met"
    elif target == SubjectStatus.ENROLLED:
        kwargs.update(
            enrollment_date=ENROLLED,
            randomization_date=ENROLLED,
            arm=StudyArm.PLACEBO.value,
        )
    elif target == SubjectStatus.COMPLETED:
        kwargs["completed_date"] = AS_OF
    elif target in {SubjectStatus.WITHDRAWN, SubjectStatus.LOST_TO_FOLLOW_UP}:
        kwargs.update(withdrawal_date=AS_OF, withdrawal_reason="Participant exited")
    kwargs.update(overrides)
    return validate_subject_transition(subject(current), target.value, **kwargs)


ALLOWED = {
    (SubjectStatus.SCREENING, SubjectStatus.SCREEN_FAILED),
    (SubjectStatus.SCREENING, SubjectStatus.ENROLLED),
    (SubjectStatus.ENROLLED, SubjectStatus.ACTIVE),
    (SubjectStatus.ENROLLED, SubjectStatus.WITHDRAWN),
    (SubjectStatus.ENROLLED, SubjectStatus.LOST_TO_FOLLOW_UP),
    (SubjectStatus.ACTIVE, SubjectStatus.COMPLETED),
    (SubjectStatus.ACTIVE, SubjectStatus.WITHDRAWN),
    (SubjectStatus.ACTIVE, SubjectStatus.LOST_TO_FOLLOW_UP),
}


@pytest.mark.parametrize("current,target", sorted(ALLOWED, key=lambda pair: (pair[0].value, pair[1].value)))
def test_every_allowed_transition(current, target):
    result = request(current, target)
    assert result.previous_status == current.value
    assert result.status == target.value


@pytest.mark.parametrize(
    "current,target",
    [
        (current, target)
        for current in SubjectStatus
        for target in SubjectStatus
        if (current, target) not in ALLOWED
    ],
)
def test_every_other_transition_pair_is_forbidden(current, target):
    with pytest.raises(SubjectTransitionError, match="not allowed") as raised:
        request(current, target)
    assert raised.value.code == "TRANSITION_NOT_ALLOWED"


@pytest.mark.parametrize(
    "terminal",
    [
        SubjectStatus.SCREEN_FAILED,
        SubjectStatus.COMPLETED,
        SubjectStatus.WITHDRAWN,
        SubjectStatus.LOST_TO_FOLLOW_UP,
    ],
)
def test_terminal_statuses_have_no_outgoing_transition(terminal):
    for target in SubjectStatus:
        with pytest.raises(SubjectTransitionError):
            request(terminal, target)


@pytest.mark.parametrize("status", list(SubjectStatus))
def test_same_status_is_forbidden(status):
    with pytest.raises(SubjectTransitionError) as raised:
        request(status, status)
    assert raised.value.code == "TRANSITION_NOT_ALLOWED"


def test_activation_preserves_enrollment_facts_and_normalizes_outcomes():
    original = subject(
        SubjectStatus.ENROLLED,
        prakriti="vata_pitta",
    )
    result = validate_subject_transition(
        original,
        SubjectStatus.ACTIVE.value,
        as_of=AS_OF,
    )
    assert result.previous_status == SubjectStatus.ENROLLED.value
    assert result.status == SubjectStatus.ACTIVE.value
    assert result.screening_date == original.screening_date
    assert result.enrollment_date == original.enrollment_date
    assert result.randomization_date == original.randomization_date
    assert result.arm == original.arm
    assert result.screen_failure_reason is None
    assert result.completed_date is None
    assert result.withdrawal_date is None
    assert result.withdrawal_reason is None
    assert original.prakriti == "vata_pitta"


@pytest.mark.parametrize("missing", ["enrollment_date", "randomization_date"])
def test_activation_requires_existing_enrollment_facts(missing):
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.ENROLLED, **{missing: None}),
            SubjectStatus.ACTIVE.value,
            as_of=AS_OF,
        )
    assert raised.value.code == "ENROLLMENT_FACTS_REQUIRED"


def test_activation_requires_a_randomized_arm():
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.ENROLLED, arm=StudyArm.NOT_RANDOMIZED.value),
            SubjectStatus.ACTIVE.value,
            as_of=AS_OF,
        )
    assert raised.value.code == "RANDOMIZED_ARM_REQUIRED"


@pytest.mark.parametrize(
    "overrides",
    [
        {"screen_failure_reason": "failed"},
        {"completed_date": AS_OF},
        {"withdrawal_date": AS_OF},
        {"withdrawal_reason": "left"},
    ],
)
def test_activation_rejects_incompatible_outcome_fields(overrides):
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.ENROLLED, **overrides),
            SubjectStatus.ACTIVE.value,
            as_of=AS_OF,
        )
    assert raised.value.code == "OUTCOME_FIELDS_MUST_BE_EMPTY"


def test_repeated_activation_is_rejected():
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ACTIVE, SubjectStatus.ACTIVE)
    assert raised.value.code == "TRANSITION_NOT_ALLOWED"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_screen_failure_requires_a_nonblank_reason(reason):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.SCREENING, SubjectStatus.SCREEN_FAILED, screen_failure_reason=reason)
    assert raised.value.code == "SCREEN_FAILURE_REASON_REQUIRED"


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"arm": StudyArm.TREATMENT.value}, "ARM_MUST_REMAIN_NOT_RANDOMIZED"),
        ({"enrollment_date": ENROLLED}, "ENROLLMENT_FIELDS_MUST_BE_EMPTY"),
        ({"randomization_date": ENROLLED}, "ENROLLMENT_FIELDS_MUST_BE_EMPTY"),
        ({"completed_date": AS_OF}, "EXIT_FIELDS_MUST_BE_EMPTY"),
        ({"withdrawal_date": AS_OF}, "EXIT_FIELDS_MUST_BE_EMPTY"),
        ({"withdrawal_reason": "exit"}, "EXIT_FIELDS_MUST_BE_EMPTY"),
    ],
)
def test_screen_failure_rejects_incompatible_existing_fields(overrides, code):
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.SCREENING, **overrides),
            SubjectStatus.SCREEN_FAILED.value,
            as_of=AS_OF,
            screen_failure_reason="Not eligible",
        )
    assert raised.value.code == code


@pytest.mark.parametrize(
    "proposed,code",
    [
        ({"arm": StudyArm.TREATMENT.value}, "ARM_MUST_REMAIN_NOT_RANDOMIZED"),
        ({"enrollment_date": ENROLLED}, "ENROLLMENT_FIELDS_MUST_BE_EMPTY"),
        ({"randomization_date": ENROLLED}, "ENROLLMENT_FIELDS_MUST_BE_EMPTY"),
        ({"completed_date": AS_OF}, "EXIT_FIELDS_MUST_BE_EMPTY"),
        ({"withdrawal_date": AS_OF}, "EXIT_FIELDS_MUST_BE_EMPTY"),
        ({"withdrawal_reason": "exit"}, "EXIT_FIELDS_MUST_BE_EMPTY"),
    ],
)
def test_screen_failure_rejects_incompatible_proposed_fields(proposed, code):
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.SCREENING),
            SubjectStatus.SCREEN_FAILED.value,
            as_of=AS_OF,
            screen_failure_reason="Not eligible",
            **proposed,
        )
    assert raised.value.code == code


@pytest.mark.parametrize("missing", ["enrollment_date", "randomization_date"])
def test_enrollment_requires_both_dates(missing):
    kwargs = {"enrollment_date": ENROLLED, "randomization_date": ENROLLED, "arm": StudyArm.TREATMENT.value}
    kwargs[missing] = None
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(subject(SubjectStatus.SCREENING), SubjectStatus.ENROLLED.value, as_of=AS_OF, **kwargs)
    assert raised.value.code == "ENROLLMENT_DATES_REQUIRED"


def test_enrollment_requires_an_existing_screening_date():
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.SCREENING, screening_date=None),
            SubjectStatus.ENROLLED.value,
            as_of=AS_OF,
            enrollment_date=ENROLLED,
            randomization_date=ENROLLED,
            arm=StudyArm.TREATMENT.value,
        )
    assert raised.value.code == "SCREENING_DATE_REQUIRED"


@pytest.mark.parametrize("arm", [None, StudyArm.NOT_RANDOMIZED.value])
def test_enrollment_requires_a_randomized_arm(arm):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.SCREENING, SubjectStatus.ENROLLED, arm=arm)
    assert raised.value.code == "RANDOMIZED_ARM_REQUIRED"


def test_enrollment_rejects_an_unknown_arm():
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.SCREENING, SubjectStatus.ENROLLED, arm="unknown")
    assert raised.value.code == "INVALID_RANDOMIZED_ARM"


@pytest.mark.parametrize(
    "overrides",
    [
        {"screen_failure_reason": "failed"},
        {"completed_date": AS_OF},
        {"withdrawal_date": AS_OF},
        {"withdrawal_reason": "exit"},
    ],
)
def test_enrollment_rejects_existing_outcome_fields(overrides):
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.SCREENING, **overrides),
            SubjectStatus.ENROLLED.value,
            as_of=AS_OF,
            enrollment_date=ENROLLED,
            randomization_date=ENROLLED,
            arm=StudyArm.TREATMENT.value,
        )
    assert raised.value.code == "OUTCOME_FIELDS_MUST_BE_EMPTY"


@pytest.mark.parametrize(
    "proposed",
    [
        {"screen_failure_reason": "failed"},
        {"completed_date": AS_OF},
        {"withdrawal_date": AS_OF},
        {"withdrawal_reason": "exit"},
    ],
)
def test_enrollment_rejects_proposed_outcome_fields(proposed):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.SCREENING, SubjectStatus.ENROLLED, **proposed)
    assert raised.value.code == "OUTCOME_FIELDS_MUST_BE_EMPTY"


@pytest.mark.parametrize(
    "screening,enrollment,randomization",
    [
        (ENROLLED + timedelta(days=1), ENROLLED, ENROLLED),
        (SCREENED, ENROLLED, ENROLLED - timedelta(days=1)),
    ],
)
def test_enrollment_dates_must_be_ordered(screening, enrollment, randomization):
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.SCREENING, screening_date=screening),
            SubjectStatus.ENROLLED.value,
            as_of=AS_OF,
            enrollment_date=enrollment,
            randomization_date=randomization,
            arm=StudyArm.TREATMENT.value,
        )
    assert raised.value.code == "ENROLLMENT_DATES_OUT_OF_ORDER"


@pytest.mark.parametrize("field", ["screening", "enrollment", "randomization"])
def test_enrollment_dates_cannot_be_in_the_future(field):
    future = AS_OF + timedelta(days=1)
    screening, enrollment, randomization = SCREENED, ENROLLED, ENROLLED
    if field == "screening":
        screening = enrollment = randomization = future
    elif field == "enrollment":
        enrollment = randomization = future
    else:
        randomization = future
    with pytest.raises(SubjectTransitionError) as raised:
        validate_subject_transition(
            subject(SubjectStatus.SCREENING, screening_date=screening),
            SubjectStatus.ENROLLED.value,
            as_of=AS_OF,
            enrollment_date=enrollment,
            randomization_date=randomization,
            arm=StudyArm.TREATMENT.value,
        )
    assert raised.value.code == "FUTURE_SUBJECT_DATE"


def test_enrollment_allows_same_enrollment_and_randomization_date_and_optional_baseline_fields():
    original = subject(SubjectStatus.SCREENING, age_at_enrollment=None, prakriti=None)
    result = validate_subject_transition(
        original,
        SubjectStatus.ENROLLED.value,
        as_of=AS_OF,
        enrollment_date=ENROLLED,
        randomization_date=ENROLLED,
        arm=StudyArm.COMPARATOR.value,
    )
    assert result.enrollment_date == result.randomization_date
    assert original.age_at_enrollment is None
    assert original.prakriti is None


@pytest.mark.parametrize("target", [SubjectStatus.WITHDRAWN, SubjectStatus.LOST_TO_FOLLOW_UP])
@pytest.mark.parametrize("reason", [None, "", "  "])
def test_exit_requires_a_nonblank_reason(target, reason):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ENROLLED, target, withdrawal_reason=reason)
    assert raised.value.code == "WITHDRAWAL_DETAILS_REQUIRED"


@pytest.mark.parametrize("target", [SubjectStatus.WITHDRAWN, SubjectStatus.LOST_TO_FOLLOW_UP])
def test_exit_requires_a_withdrawal_date(target):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ACTIVE, target, withdrawal_date=None)
    assert raised.value.code == "WITHDRAWAL_DETAILS_REQUIRED"


@pytest.mark.parametrize("target", [SubjectStatus.WITHDRAWN, SubjectStatus.LOST_TO_FOLLOW_UP])
@pytest.mark.parametrize(
    "withdrawal_date,code",
    [
        (ENROLLED - timedelta(days=1), "WITHDRAWAL_BEFORE_ENROLLMENT"),
        (AS_OF + timedelta(days=1), "FUTURE_WITHDRAWAL_DATE"),
    ],
)
def test_exit_date_boundaries(target, withdrawal_date, code):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ACTIVE, target, withdrawal_date=withdrawal_date)
    assert raised.value.code == code


@pytest.mark.parametrize("target", [SubjectStatus.WITHDRAWN, SubjectStatus.LOST_TO_FOLLOW_UP])
def test_exit_may_occur_on_the_enrollment_date(target):
    result = request(
        SubjectStatus.ENROLLED,
        target,
        withdrawal_date=ENROLLED,
        withdrawal_reason="  Participant exited  ",
    )
    assert result.withdrawal_date == ENROLLED
    assert result.withdrawal_reason == "Participant exited"


@pytest.mark.parametrize("target", [SubjectStatus.WITHDRAWN, SubjectStatus.LOST_TO_FOLLOW_UP])
def test_exit_rejects_completion_and_screen_failure_fields(target):
    for overrides, code in [
        ({"completed_date": AS_OF}, "COMPLETION_FIELD_MUST_BE_EMPTY"),
        ({"screen_failure_reason": "failed"}, "SCREEN_FAILURE_REASON_MUST_BE_EMPTY"),
    ]:
        with pytest.raises(SubjectTransitionError) as raised:
            validate_subject_transition(
                subject(SubjectStatus.ACTIVE, **overrides),
                target.value,
                as_of=AS_OF,
                withdrawal_date=AS_OF,
                withdrawal_reason="exit",
            )
        assert raised.value.code == code


@pytest.mark.parametrize("target", [SubjectStatus.WITHDRAWN, SubjectStatus.LOST_TO_FOLLOW_UP])
@pytest.mark.parametrize(
    "proposed,code",
    [
        ({"completed_date": AS_OF}, "COMPLETION_FIELD_MUST_BE_EMPTY"),
        ({"screen_failure_reason": "failed"}, "SCREEN_FAILURE_REASON_MUST_BE_EMPTY"),
    ],
)
def test_exit_rejects_proposed_completion_and_screen_failure_fields(target, proposed, code):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ACTIVE, target, **proposed)
    assert raised.value.code == code


def test_completion_requires_a_date():
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ACTIVE, SubjectStatus.COMPLETED, completed_date=None)
    assert raised.value.code == "COMPLETION_DATE_REQUIRED"


@pytest.mark.parametrize(
    "completed_date,code",
    [
        (ENROLLED - timedelta(days=1), "COMPLETION_BEFORE_ENROLLMENT"),
        (AS_OF + timedelta(days=1), "FUTURE_COMPLETION_DATE"),
    ],
)
def test_completion_date_boundaries(completed_date, code):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ACTIVE, SubjectStatus.COMPLETED, completed_date=completed_date)
    assert raised.value.code == code


def test_completion_rejects_withdrawal_and_screen_failure_fields():
    for overrides, code in [
        ({"withdrawal_date": AS_OF}, "WITHDRAWAL_FIELDS_MUST_BE_EMPTY"),
        ({"withdrawal_reason": "exit"}, "WITHDRAWAL_FIELDS_MUST_BE_EMPTY"),
        ({"screen_failure_reason": "failed"}, "SCREEN_FAILURE_REASON_MUST_BE_EMPTY"),
    ]:
        with pytest.raises(SubjectTransitionError) as raised:
            validate_subject_transition(
                subject(SubjectStatus.ACTIVE, **overrides),
                SubjectStatus.COMPLETED.value,
                as_of=AS_OF,
                completed_date=AS_OF,
            )
        assert raised.value.code == code


@pytest.mark.parametrize(
    "proposed,code",
    [
        ({"withdrawal_date": AS_OF}, "WITHDRAWAL_FIELDS_MUST_BE_EMPTY"),
        ({"withdrawal_reason": "exit"}, "WITHDRAWAL_FIELDS_MUST_BE_EMPTY"),
        ({"screen_failure_reason": "failed"}, "SCREEN_FAILURE_REASON_MUST_BE_EMPTY"),
    ],
)
def test_completion_rejects_proposed_withdrawal_and_screen_failure_fields(proposed, code):
    with pytest.raises(SubjectTransitionError) as raised:
        request(SubjectStatus.ACTIVE, SubjectStatus.COMPLETED, **proposed)
    assert raised.value.code == code


def test_completion_has_no_synthetic_84_day_minimum():
    result = validate_subject_transition(
        subject(SubjectStatus.ACTIVE, enrollment_date=AS_OF),
        SubjectStatus.COMPLETED.value,
        as_of=AS_OF,
        completed_date=AS_OF,
    )
    assert result.completed_date == AS_OF


def test_supplied_subject_is_not_mutated():
    original = subject(SubjectStatus.SCREENING)
    before = original.model_dump()
    result = validate_subject_transition(
        original,
        SubjectStatus.ENROLLED.value,
        as_of=AS_OF,
        enrollment_date=ENROLLED,
        randomization_date=ENROLLED,
        arm=StudyArm.PLACEBO.value,
    )
    assert original.model_dump() == before
    assert original.status == SubjectStatus.SCREENING.value
    assert result.status == SubjectStatus.ENROLLED.value
