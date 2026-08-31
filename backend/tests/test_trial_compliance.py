"""Focused tests for the pure trial activation compliance checker."""

from copy import deepcopy
from datetime import date

import pytest

from app.enums import EthicsApprovalStatus, TrialPhase, TrialStatus
from app.models import Trial
from app.services.trial_compliance import check_activation_eligibility

AS_OF = date(2026, 8, 25)


def compliant_trial(**changes) -> Trial:
    values = {
        "protocol_number": "AIIA-ASH-2026-01",
        "title": "Compliant clinical trial",
        "short_title": "Compliant Trial",
        "ctri_number": "CTRI/2026/01/078412",
        "ctri_registration_date": date(2025, 12, 10),
        "phase": TrialPhase.PHASE_3.value,
        "status": TrialStatus.APPROVED.value,
        "indication": "Generalised Anxiety Disorder",
        "intervention": "Study medicine twice daily",
        "design": "Randomised controlled trial",
        "sponsor_name": "All India Institute of Ayurveda",
        "target_enrollment": 240,
        "start_date": date(2026, 1, 1),
        "planned_end_date": date(2027, 6, 25),
        "ethics_approval_number": "AIIA/IEC/2025/114",
        "ethics_approval_date": date(2025, 11, 15),
        "ethics_approval_status": EthicsApprovalStatus.APPROVED.value,
        "ethics_approval_valid_until": date(2026, 12, 31),
        "regulatory_approval_number": "CDSCO/AYUSH/CT/2025/0391",
        "regulatory_approval_date": date(2025, 12, 1),
    }
    values.update(changes)
    return Trial(**values)


def blocker_codes(trial: Trial) -> list[str]:
    return [
        blocker.code
        for blocker in check_activation_eligibility(trial, AS_OF).blockers
    ]


def test_fully_compliant_trial_is_eligible() -> None:
    result = check_activation_eligibility(compliant_trial(), AS_OF)
    assert result.eligible_for_activation is True
    assert result.blockers == ()
    assert result.checks and all(check.passed for check in result.checks)


def test_check_does_not_modify_trial() -> None:
    trial = compliant_trial()
    before = deepcopy(trial.model_dump())
    check_activation_eligibility(trial, AS_OF)
    assert trial.model_dump() == before


@pytest.mark.parametrize(
    "changes",
    [
        {"protocol_number": ""},
        {"title": ""},
        {"phase": ""},
        {"intervention": ""},
        {"sponsor_name": ""},
        {"start_date": None},
        {"planned_end_date": None},
    ],
)
def test_missing_protocol_field_blocks_activation(changes: dict) -> None:
    assert "PROTOCOL_INCOMPLETE" in blocker_codes(compliant_trial(**changes))


def test_target_enrolment_zero_blocks_activation() -> None:
    assert "PROTOCOL_INCOMPLETE" in blocker_codes(
        compliant_trial(target_enrollment=0)
    )


def test_planned_end_before_start_blocks_activation() -> None:
    codes = blocker_codes(compliant_trial(planned_end_date=date(2025, 12, 31)))
    assert "INVALID_TRIAL_DATES" in codes


def test_pending_ethics_approval_blocks_activation() -> None:
    codes = blocker_codes(
        compliant_trial(ethics_approval_status=EthicsApprovalStatus.PENDING.value)
    )
    assert "ETHICS_NOT_APPROVED" in codes


@pytest.mark.parametrize(
    "changes",
    [
        {"ethics_approval_number": None},
        {"ethics_approval_date": None},
        {"ethics_approval_valid_until": None},
    ],
)
def test_missing_ethics_information_blocks_activation(changes: dict) -> None:
    assert "ETHICS_DETAILS_MISSING" in blocker_codes(compliant_trial(**changes))


def test_expired_ethics_approval_blocks_activation() -> None:
    codes = blocker_codes(
        compliant_trial(ethics_approval_valid_until=date(2026, 8, 24))
    )
    assert "ETHICS_APPROVAL_EXPIRED" in codes


def test_ethics_approval_expiring_on_as_of_is_valid() -> None:
    result = check_activation_eligibility(
        compliant_trial(ethics_approval_valid_until=AS_OF), AS_OF
    )
    assert result.eligible_for_activation is True


def test_missing_ctri_blocks_activation() -> None:
    assert "CTRI_MISSING" in blocker_codes(compliant_trial(ctri_number=None))


def test_future_ctri_date_blocks_activation() -> None:
    codes = blocker_codes(
        compliant_trial(ctri_registration_date=date(2026, 8, 26))
    )
    assert "CTRI_DATE_INVALID" in codes


def test_missing_regulatory_approval_blocks_activation() -> None:
    codes = blocker_codes(compliant_trial(regulatory_approval_number=None))
    assert "REGULATORY_APPROVAL_MISSING" in codes


def test_future_regulatory_date_blocks_activation() -> None:
    codes = blocker_codes(
        compliant_trial(regulatory_approval_date=date(2026, 8, 26))
    )
    assert "REGULATORY_DATE_INVALID" in codes


def test_recruiting_trial_returns_already_recruiting() -> None:
    codes = blocker_codes(compliant_trial(status=TrialStatus.RECRUITING.value))
    assert "ALREADY_RECRUITING" in codes
    assert "TRIAL_STATUS_NOT_ACTIVATABLE" not in codes


def test_completed_trial_cannot_activate() -> None:
    codes = blocker_codes(compliant_trial(status=TrialStatus.COMPLETED.value))
    assert "TRIAL_STATUS_NOT_ACTIVATABLE" in codes


def test_blocker_codes_are_stable_and_not_duplicated() -> None:
    trial = compliant_trial(
        protocol_number="",
        title="",
        target_enrollment=0,
        ethics_approval_status=EthicsApprovalStatus.PENDING.value,
        ethics_approval_number=None,
        ethics_approval_date=None,
        ethics_approval_valid_until=None,
        ctri_number=None,
        ctri_registration_date=None,
        regulatory_approval_number=None,
        regulatory_approval_date=None,
        status=TrialStatus.COMPLETED.value,
    )
    codes = blocker_codes(trial)
    assert len(codes) == len(set(codes))
    assert set(codes) <= {
        "PROTOCOL_INCOMPLETE",
        "INVALID_TRIAL_DATES",
        "ETHICS_NOT_APPROVED",
        "ETHICS_DETAILS_MISSING",
        "ETHICS_VALIDITY_INVALID",
        "ETHICS_APPROVAL_EXPIRED",
        "CTRI_MISSING",
        "CTRI_DATE_INVALID",
        "REGULATORY_APPROVAL_MISSING",
        "REGULATORY_DATE_INVALID",
        "ALREADY_RECRUITING",
        "TRIAL_STATUS_NOT_ACTIVATABLE",
    }
