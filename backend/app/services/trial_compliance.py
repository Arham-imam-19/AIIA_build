"""Read-only checks for whether a trial may move into recruiting status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.enums import EthicsApprovalStatus, TrialStatus
from app.models.trial import Trial


@dataclass(frozen=True)
class ComplianceCheck:
    code: str
    passed: bool
    message: str


@dataclass(frozen=True)
class ActivationBlocker:
    code: str
    message: str


@dataclass(frozen=True)
class ActivationEligibilityResult:
    eligible_for_activation: bool
    checks: tuple[ComplianceCheck, ...]
    blockers: tuple[ActivationBlocker, ...]


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def check_activation_eligibility(
    trial: Trial, as_of: date | None = None
) -> ActivationEligibilityResult:
    """Evaluate activation prerequisites without reading or changing persistence."""
    evaluation_date = as_of or date.today()
    checks: list[ComplianceCheck] = []
    blockers: dict[str, ActivationBlocker] = {}

    def record(code: str, passed: bool, message: str) -> None:
        checks.append(ComplianceCheck(code=code, passed=passed, message=message))
        if not passed and code not in blockers:
            blockers[code] = ActivationBlocker(code=code, message=message)

    protocol_complete = (
        _present(trial.protocol_number)
        and _present(trial.title)
        and _present(trial.phase)
        and _present(trial.intervention)
        and _present(trial.sponsor_name)
        and trial.target_enrollment > 0
        and trial.start_date is not None
        and trial.planned_end_date is not None
    )
    record(
        "PROTOCOL_INCOMPLETE",
        protocol_complete,
        "Protocol fields, trial dates, and a positive target enrolment are required.",
    )

    trial_dates_valid = (
        trial.start_date is not None
        and trial.planned_end_date is not None
        and trial.planned_end_date >= trial.start_date
    )
    record(
        "INVALID_TRIAL_DATES",
        trial_dates_valid,
        "The planned end date must be on or after the trial start date.",
    )

    record(
        "ETHICS_NOT_APPROVED",
        trial.ethics_approval_status == EthicsApprovalStatus.APPROVED.value,
        "Ethics approval status must be approved.",
    )

    ethics_details_present = (
        _present(trial.ethics_approval_number)
        and trial.ethics_approval_date is not None
        and trial.ethics_approval_valid_until is not None
    )
    record(
        "ETHICS_DETAILS_MISSING",
        ethics_details_present,
        "Ethics approval number, approval date, and validity date are required.",
    )

    ethics_validity_ordered = (
        trial.ethics_approval_date is not None
        and trial.ethics_approval_valid_until is not None
        and trial.ethics_approval_valid_until >= trial.ethics_approval_date
    )
    record(
        "ETHICS_VALIDITY_INVALID",
        ethics_validity_ordered,
        "Ethics approval validity cannot end before its approval date.",
    )

    ethics_current = (
        trial.ethics_approval_valid_until is not None
        and trial.ethics_approval_valid_until >= evaluation_date
    )
    record(
        "ETHICS_APPROVAL_EXPIRED",
        ethics_current,
        "Ethics approval must remain valid through the evaluation date.",
    )

    ctri_present = _present(trial.ctri_number) and trial.ctri_registration_date is not None
    record(
        "CTRI_MISSING",
        ctri_present,
        "CTRI number and registration date are required.",
    )

    ctri_date_valid = (
        trial.ctri_registration_date is not None
        and trial.ctri_registration_date <= evaluation_date
        and trial.start_date is not None
        and trial.ctri_registration_date <= trial.start_date
    )
    record(
        "CTRI_DATE_INVALID",
        ctri_date_valid,
        "CTRI registration must not be after the evaluation or trial start date.",
    )

    regulatory_present = (
        _present(trial.regulatory_approval_number)
        and trial.regulatory_approval_date is not None
    )
    record(
        "REGULATORY_APPROVAL_MISSING",
        regulatory_present,
        "Regulatory approval number and date are required.",
    )

    regulatory_date_valid = (
        trial.regulatory_approval_date is not None
        and trial.regulatory_approval_date <= evaluation_date
        and trial.start_date is not None
        and trial.regulatory_approval_date <= trial.start_date
    )
    record(
        "REGULATORY_DATE_INVALID",
        regulatory_date_valid,
        "Regulatory approval must not be after the evaluation or trial start date.",
    )

    activatable_statuses = {
        TrialStatus.PLANNING.value,
        TrialStatus.PENDING_ETHICS.value,
        TrialStatus.APPROVED.value,
    }
    if trial.status == TrialStatus.RECRUITING.value:
        record(
            "ALREADY_RECRUITING",
            False,
            "The trial is already recruiting.",
        )
    elif trial.status not in activatable_statuses:
        record(
            "TRIAL_STATUS_NOT_ACTIVATABLE",
            False,
            f"Trial status '{trial.status}' is not eligible for activation.",
        )
    else:
        record(
            "TRIAL_STATUS_ACTIVATABLE",
            True,
            "The trial status may be evaluated for activation.",
        )

    blocker_values = tuple(blockers.values())
    return ActivationEligibilityResult(
        eligible_for_activation=not blocker_values,
        checks=tuple(checks),
        blockers=blocker_values,
    )


def check_ethics_clearance_for_enrollment(
    trial: Trial, as_of: date | None = None
) -> tuple[bool, str | None]:
    """Verify that a trial has valid, active Institutional Ethics Committee (IEC) approval.

    Under NDCT Rules 2019 (Rule 22) and GCP guidelines, no participant may be screened
    or enrolled without active ethics committee approval.
    """
    evaluation_date = as_of or date.today()
    if trial.ethics_approval_status != EthicsApprovalStatus.APPROVED.value:
        return (
            False,
            f"Institutional Ethics Committee (IEC) approval is required before screening or enrolling participants (Current status: '{trial.ethics_approval_status}').",
        )
    if not trial.ethics_approval_number or not trial.ethics_approval_number.strip():
        return (
            False,
            "IEC approval number is missing from the trial record.",
        )
    if trial.ethics_approval_valid_until is not None and trial.ethics_approval_valid_until < evaluation_date:
        return (
            False,
            f"IEC approval expired on {trial.ethics_approval_valid_until.isoformat()}; screening and enrollment are blocked.",
        )
    return (True, None)

