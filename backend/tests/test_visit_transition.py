"""Focused unit tests for the pure Visit outcome policy."""

from datetime import date, timedelta

import pytest

from app.enums import VisitStatus
from app.models import Visit
from app.services.visit_transition import VisitTransitionError, validate_visit_transition


TODAY = date(2026, 8, 27)


def visit(*, status: str = VisitStatus.SCHEDULED.value, scheduled=TODAY) -> Visit:
    return Visit(
        subject_id=1, trial_id=1, visit_name="Week 4", visit_number=2,
        visit_day=28, scheduled_date=scheduled, status=status,
    )


def transition(row: Visit, status="completed", **changes):
    values = dict(
        actual_date=TODAY, is_protocol_deviation=False,
        deviation_description=None, acting_user_id=7, as_of=TODAY,
    )
    values.update(changes)
    return validate_visit_transition(row, status, **values)


@pytest.mark.parametrize("offset", [-3, 0, 3])
def test_inclusive_window_completion_is_not_automatic_deviation(offset):
    result = transition(visit(scheduled=TODAY - timedelta(days=offset)))
    assert result.status == VisitStatus.COMPLETED.value
    assert result.is_protocol_deviation is False
    assert result.performed_by_user_id == 7


@pytest.mark.parametrize("offset", [-4, 4])
def test_outside_window_requires_documented_deviation(offset):
    row = visit(scheduled=TODAY - timedelta(days=offset))
    with pytest.raises(VisitTransitionError, match="requires deviation_description"):
        transition(row)
    result = transition(row, deviation_description="  Timing deviation.  ")
    assert result.is_protocol_deviation is True
    assert result.deviation_description == "Timing deviation."


def test_manual_in_window_deviation_requires_description():
    with pytest.raises(VisitTransitionError) as caught:
        transition(visit(), is_protocol_deviation=True)
    assert caught.value.code == "DEVIATION_DESCRIPTION_REQUIRED"
    result = transition(
        visit(), is_protocol_deviation=True,
        deviation_description="  Assessment omitted. ",
    )
    assert result.deviation_description == "Assessment omitted."


def test_description_is_cleared_when_deviation_is_false():
    result = transition(visit(), deviation_description="unused")
    assert result.deviation_description is None


def test_future_completion_fails():
    with pytest.raises(VisitTransitionError) as caught:
        transition(visit(), actual_date=TODAY + timedelta(days=1))
    assert caught.value.code == "ACTUAL_DATE_IN_FUTURE"


def test_missed_after_window_normalizes_values():
    result = transition(
        visit(scheduled=TODAY - timedelta(days=4)), status="missed",
        actual_date=None, is_protocol_deviation=False,
        deviation_description="  Could not contact participant. ",
    )
    assert result.is_protocol_deviation is True
    assert result.actual_date is None
    assert result.performed_by_user_id is None
    assert result.deviation_description == "Could not contact participant."


@pytest.mark.parametrize("days_ago", [0, 3])
def test_missed_on_or_before_window_boundary_fails(days_ago):
    with pytest.raises(VisitTransitionError) as caught:
        transition(
            visit(scheduled=TODAY - timedelta(days=days_ago)), status="missed",
            actual_date=None, deviation_description="Absent",
        )
    assert caught.value.code == "VISIT_WINDOW_OPEN"


def test_missed_forbids_actual_date():
    with pytest.raises(VisitTransitionError) as caught:
        transition(
            visit(scheduled=TODAY - timedelta(days=4)), status="missed",
            deviation_description="Absent",
        )
    assert caught.value.code == "ACTUAL_DATE_FORBIDDEN"


@pytest.mark.parametrize("current", [
    VisitStatus.COMPLETED.value, VisitStatus.MISSED.value,
    VisitStatus.CANCELLED.value, VisitStatus.IN_PROGRESS.value,
])
def test_non_scheduled_and_repeated_transitions_fail(current):
    with pytest.raises(VisitTransitionError) as caught:
        transition(visit(status=current))
    assert caught.value.code == "TRANSITION_NOT_ALLOWED"


def test_missing_schedule_fails_without_mutating_input():
    row = visit(scheduled=None)
    before = row.model_dump()
    with pytest.raises(VisitTransitionError) as caught:
        transition(row)
    assert caught.value.code == "SCHEDULED_DATE_REQUIRED"
    assert row.model_dump() == before


def test_success_does_not_mutate_input():
    row = visit()
    before = row.model_dump()
    transition(row)
    assert row.model_dump() == before