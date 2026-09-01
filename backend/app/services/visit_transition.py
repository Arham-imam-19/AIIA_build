"""Pure validation for recording an outcome on an existing study Visit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.enums import VisitStatus
from app.models.visit import Visit


class VisitTransitionError(ValueError):
    """A requested Visit outcome violates the lifecycle policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VisitTransitionResult:
    """Normalized outcome values for the caller to persist atomically."""

    previous_status: str
    status: str
    scheduled_date: date
    actual_date: date | None
    is_protocol_deviation: bool
    deviation_description: str | None
    performed_by_user_id: int | None


def _reject(code: str, message: str) -> None:
    raise VisitTransitionError(code, message)


def _description(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else None
    if not normalized:
        return None
    if len(normalized) > 1000:
        _reject(
            "DEVIATION_DESCRIPTION_TOO_LONG",
            "deviation_description must not exceed 1000 characters",
        )
    return normalized


def validate_visit_transition(
    visit: Visit,
    target_status: str,
    *,
    actual_date: date | None,
    is_protocol_deviation: bool,
    deviation_description: str | None,
    acting_user_id: int,
    as_of: date,
) -> VisitTransitionResult:
    """Validate and normalize one Visit outcome without mutating ``visit``."""
    if visit.status != VisitStatus.SCHEDULED.value or target_status not in {
        VisitStatus.COMPLETED.value,
        VisitStatus.MISSED.value,
    }:
        _reject(
            "TRANSITION_NOT_ALLOWED",
            f"visit cannot transition from {visit.status!r} to {target_status!r}",
        )
    if visit.scheduled_date is None:
        _reject("SCHEDULED_DATE_REQUIRED", "visit must have a scheduled_date")

    description = _description(deviation_description)
    if target_status == VisitStatus.COMPLETED.value:
        if actual_date is None:
            _reject("ACTUAL_DATE_REQUIRED", "completed visit requires actual_date")
        if actual_date > as_of:
            _reject("ACTUAL_DATE_IN_FUTURE", "actual_date must not be in the future")
        outside_window = abs((actual_date - visit.scheduled_date).days) > 3
        normalized_deviation = is_protocol_deviation or outside_window
        if normalized_deviation and description is None:
            _reject(
                "DEVIATION_DESCRIPTION_REQUIRED",
                "a protocol deviation requires deviation_description",
            )
        if not normalized_deviation:
            description = None
        return VisitTransitionResult(
            visit.status, VisitStatus.COMPLETED.value, visit.scheduled_date,
            actual_date, normalized_deviation, description, acting_user_id,
        )

    if actual_date is not None:
        _reject("ACTUAL_DATE_FORBIDDEN", "missed visit must not have actual_date")
    if as_of <= visit.scheduled_date + timedelta(days=3):
        _reject(
            "VISIT_WINDOW_OPEN",
            "visit cannot be marked missed until its protocol window has passed",
        )
    if description is None:
        _reject(
            "DEVIATION_DESCRIPTION_REQUIRED",
            "a missed visit requires deviation_description",
        )
    return VisitTransitionResult(
        visit.status, VisitStatus.MISSED.value, visit.scheduled_date,
        None, True, description, None,
    )
