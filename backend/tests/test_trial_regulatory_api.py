"""Focused API tests for replacing a trial's regulatory-approval state."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import func
from sqlmodel import Session, select

from app.enums import AuditAction, TrialPhase, TrialStatus, UserRole
from app.models import AuditLog, Trial
from app.models.base import utcnow


def first_trial(session: Session) -> Trial:
    trial = session.exec(select(Trial).order_by(Trial.id)).first()
    assert trial is not None
    return trial


def audit_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(AuditLog)).one()


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def valid_date(trial: Trial) -> date:
    return min(utc_today(), trial.start_date or utc_today())


def body(number: str | None, approval_date: date | str | None) -> dict:
    return {
        "regulatory_approval_number": number,
        "regulatory_approval_date": (
            str(approval_date) if approval_date is not None else None
        ),
    }


def patch(role_clients, target_id: int, payload: dict):
    return role_clients[UserRole.SPONSOR.value].patch(
        f"/api/trials/{target_id}/regulatory-approval",
        json=payload,
    )


def set_trial_state(
    seeded_engine,
    *,
    number: str | None = None,
    approval_date: date | None = None,
    start_date: date | None | object = ...,
    activated_at: datetime | None = None,
) -> int:
    with Session(seeded_engine) as session:
        trial = first_trial(session)
        trial.regulatory_approval_number = number
        trial.regulatory_approval_date = approval_date
        if start_date is not ...:
            trial.start_date = start_date
        trial.activated_at = activated_at
        session.add(trial)
        session.commit()
        assert trial.id is not None
        return trial.id


@pytest.mark.parametrize("role", [UserRole.SPONSOR])
def test_sponsor_and_admin_can_update_and_number_is_trimmed(
    role_clients, seeded_engine, role
):
    target_id = set_trial_state(seeded_engine)
    with Session(seeded_engine) as session:
        approval_date = valid_date(session.get(Trial, target_id))
        before_updated_at = session.get(Trial, target_id).updated_at

    response = patch(
        role_clients[role.value],
        target_id,
        body(f"  SYNTHETIC-REGULATORY-{role.value}  ", approval_date),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "trial_id": target_id,
        "protocol_number": payload["protocol_number"],
        "regulatory_approval_number": f"SYNTHETIC-REGULATORY-{role.value}",
        "regulatory_approval_date": str(approval_date),
        "updated_at": payload["updated_at"],
    }

    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.regulatory_approval_number == (
            f"SYNTHETIC-REGULATORY-{role.value}"
        )
        assert trial.regulatory_approval_date == approval_date
        assert trial.updated_at > before_updated_at


def test_explicit_null_pair_clears_before_activation_and_audits_once(
    role_clients, seeded_engine
):
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-REGULATORY-TO-CLEAR",
        approval_date=utc_today() - timedelta(days=30),
    )
    with Session(seeded_engine) as session:
        before_audits = audit_count(session)

    response = patch(role_clients, target_id, body(None, None))
    assert response.status_code == 200, response.text
    assert response.json()["regulatory_approval_number"] is None
    assert response.json()["regulatory_approval_date"] is None

    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.regulatory_approval_number is None
        assert trial.regulatory_approval_date is None
        assert audit_count(session) == before_audits + 1
        entry = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert entry.reason == "Trial regulatory approval cleared."


def test_anonymous_request_returns_401_without_side_effects(
    anonymous_role_clients, seeded_engine
):
    target_id = set_trial_state(seeded_engine)
    assert_failure_without_side_effects(
        anonymous_role_clients,
        seeded_engine,
        target_id,
        body("SYNTHETIC-DENIED", utc_today() - timedelta(days=30)),
        expected_status=401,
    )


@pytest.mark.parametrize(
    "role",
    [
        UserRole.REGULATOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
    ],
)
def test_unauthorized_roles_receive_403_without_side_effects(
    role_clients, seeded_engine, role
):
    target_id = set_trial_state(seeded_engine)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        approval_date = valid_date(trial)
    assert_failure_without_side_effects(
        role_clients[role.value],
        seeded_engine,
        target_id,
        body("SYNTHETIC-DENIED", approval_date),
        expected_status=403,
    )


def test_missing_trial_uses_existing_404_format_without_audit(role_clients, seeded_engine):
    with Session(seeded_engine) as session:
        before_audits = audit_count(session)
    response = patch(role_clients, 999999, body(None, None))
    assert response.status_code == 404
    assert response.json()["detail"] == "no trial with id 999999"
    with Session(seeded_engine) as session:
        assert audit_count(session) == before_audits


@pytest.mark.parametrize(
    "payload",
    [
        {"regulatory_approval_number": None},
        {"regulatory_approval_date": None},
        {
            "regulatory_approval_number": None,
            "regulatory_approval_date": None,
            "unexpected": "not allowed",
        },
        body("", utc_today() - timedelta(days=1)),
        body("   ", utc_today() - timedelta(days=1)),
        body("X" * 121, utc_today() - timedelta(days=1)),
        body("SYNTHETIC-NUMBER-ONLY", None),
        body(None, utc_today() - timedelta(days=1)),
        body("SYNTHETIC-INVALID-DATE", "not-a-date"),
        body("SYNTHETIC-FUTURE", utc_today() + timedelta(days=1)),
    ],
)
def test_invalid_requests_do_not_mutate_or_audit(role_clients, seeded_engine, payload):
    target_id = set_trial_state(seeded_engine)
    assert_failure_without_side_effects(
        role_clients, seeded_engine, target_id, payload, expected_status=422
    )


def test_approval_date_after_trial_start_is_rejected(role_clients, seeded_engine):
    start = utc_today() - timedelta(days=10)
    target_id = set_trial_state(seeded_engine, start_date=start)
    assert_failure_without_side_effects(
        role_clients,
        seeded_engine,
        target_id,
        body("SYNTHETIC-AFTER-START", start + timedelta(days=1)),
        expected_status=422,
    )


def test_approval_date_equal_to_trial_start_is_accepted(role_clients, seeded_engine):
    start = utc_today() - timedelta(days=10)
    target_id = set_trial_state(seeded_engine, start_date=start)
    response = patch(role_clients, target_id, body("SYNTHETIC-ON-START", start))
    assert response.status_code == 200, response.text
    assert response.json()["regulatory_approval_date"] == str(start)


def test_approval_can_be_stored_without_trial_start_date(role_clients, seeded_engine):
    target_id = set_trial_state(seeded_engine, start_date=None)
    approval_date = utc_today()
    response = patch(
        role_clients, target_id, body("SYNTHETIC-NO-START", approval_date)
    )
    assert response.status_code == 200, response.text
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.start_date is None
        assert trial.regulatory_approval_date == approval_date


def test_identical_normalized_request_is_noop(role_clients, seeded_engine):
    approval_date = utc_today() - timedelta(days=20)
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-REGULATORY-NOOP",
        approval_date=approval_date,
    )
    with Session(seeded_engine) as session:
        before_updated_at = session.get(Trial, target_id).updated_at
        before_audits = audit_count(session)

    response = patch(
        role_clients,
        target_id,
        body("  SYNTHETIC-REGULATORY-NOOP  ", approval_date),
    )
    assert response.status_code == 200, response.text
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.updated_at == before_updated_at
        assert audit_count(session) == before_audits


def test_identical_noop_remains_allowed_after_activation(role_clients, seeded_engine):
    approval_date = utc_today() - timedelta(days=20)
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-ACTIVATED-NOOP",
        approval_date=approval_date,
        activated_at=utcnow() - timedelta(days=1),
    )
    with Session(seeded_engine) as session:
        before_updated_at = session.get(Trial, target_id).updated_at
        before_audits = audit_count(session)

    response = patch(
        role_clients,
        target_id,
        body("  SYNTHETIC-ACTIVATED-NOOP  ", approval_date),
    )
    assert response.status_code == 200, response.text
    with Session(seeded_engine) as session:
        assert session.get(Trial, target_id).updated_at == before_updated_at
        assert audit_count(session) == before_audits


@pytest.mark.parametrize("clearing", [False, True])
def test_change_or_clearing_after_activation_returns_409_without_side_effects(
    role_clients, seeded_engine, clearing
):
    approval_date = utc_today() - timedelta(days=20)
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-ACTIVATED",
        approval_date=approval_date,
        activated_at=utcnow() - timedelta(days=1),
    )
    payload = (
        body(None, None)
        if clearing
        else body("SYNTHETIC-ACTIVATED-CHANGED", approval_date)
    )
    assert_failure_without_side_effects(
        role_clients, seeded_engine, target_id, payload, expected_status=409
    )


def test_successful_change_audits_once_and_preserves_unrelated_fields(
    role_clients, seeded_engine
):
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-REGULATORY-OLD",
        approval_date=utc_today() - timedelta(days=40),
    )
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        approval_date = valid_date(trial)
        protected = {
            "status": trial.status,
            "start_date": trial.start_date,
            "planned_end_date": trial.planned_end_date,
            "actual_end_date": trial.actual_end_date,
            "activated_at": trial.activated_at,
            "activated_by_user_id": trial.activated_by_user_id,
            "ctri_number": trial.ctri_number,
            "ctri_registration_date": trial.ctri_registration_date,
            "ethics_approval_number": trial.ethics_approval_number,
            "ethics_approval_date": trial.ethics_approval_date,
            "ethics_approval_status": trial.ethics_approval_status,
            "ethics_approval_valid_until": trial.ethics_approval_valid_until,
        }
        before_updated_at = trial.updated_at
        before_audits = audit_count(session)

    response = patch(
        role_clients,
        target_id,
        body("SYNTHETIC-REGULATORY-AUDITED", approval_date),
    )
    assert response.status_code == 200, response.text

    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.updated_at > before_updated_at
        assert audit_count(session) == before_audits + 1
        assert {
            "status": trial.status,
            "start_date": trial.start_date,
            "planned_end_date": trial.planned_end_date,
            "actual_end_date": trial.actual_end_date,
            "activated_at": trial.activated_at,
            "activated_by_user_id": trial.activated_by_user_id,
            "ctri_number": trial.ctri_number,
            "ctri_registration_date": trial.ctri_registration_date,
            "ethics_approval_number": trial.ethics_approval_number,
            "ethics_approval_date": trial.ethics_approval_date,
            "ethics_approval_status": trial.ethics_approval_status,
            "ethics_approval_valid_until": trial.ethics_approval_valid_until,
        } == protected

        entry = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert entry.action == AuditAction.UPDATE.value
        assert entry.entity_type == "trials"
        assert entry.entity_id == target_id
        assert entry.entity_label == trial.protocol_number
        assert entry.field_name == "regulatory_approval_number"
        assert entry.trial_id == target_id
        assert json.loads(entry.old_value) == {
            "regulatory_approval_date": str(utc_today() - timedelta(days=40)),
            "regulatory_approval_number": "SYNTHETIC-REGULATORY-OLD",
        }
        assert json.loads(entry.new_value) == {
            "regulatory_approval_date": str(approval_date),
            "regulatory_approval_number": "SYNTHETIC-REGULATORY-AUDITED",
        }
        assert entry.reason == "Trial regulatory approval updated."


def test_regulatory_approval_numbers_are_not_api_unique(role_clients, seeded_engine):
    duplicate = "SYNTHETIC-REGULATORY-SHARED"
    with Session(seeded_engine) as session:
        target = first_trial(session)
        target.regulatory_approval_number = None
        target.regulatory_approval_date = None
        target.activated_at = None
        approval_date = valid_date(target)
        other = Trial(
            protocol_number="SYNTHETIC-PROTOCOL-REGULATORY-DUPLICATE",
            title="Synthetic shared regulatory approval owner",
            short_title="Synthetic shared approval",
            phase=TrialPhase.PHASE_1.value,
            status=TrialStatus.PLANNING.value,
            indication="Synthetic indication",
            intervention="Synthetic intervention",
            design="Synthetic design",
            sponsor_name="Synthetic sponsor",
            regulatory_approval_number=duplicate,
            regulatory_approval_date=approval_date,
        )
        session.add(target)
        session.add(other)
        session.commit()
        target_id = target.id
        assert target_id is not None

    response = patch(role_clients, target_id, body(duplicate, approval_date))
    assert response.status_code == 200, response.text
    with Session(seeded_engine) as session:
        owners = session.exec(
            select(Trial).where(Trial.regulatory_approval_number == duplicate)
        ).all()
        assert len(owners) == 2


def assert_failure_without_side_effects(
    role_clients,
    seeded_engine,
    target_id: int,
    payload: dict,
    *,
    expected_status: int,
) -> None:
    with Session(seeded_engine) as session:
        before = deepcopy(session.get(Trial, target_id).model_dump())
        before_audits = audit_count(session)

    response = patch(role_clients, target_id, payload)
    assert response.status_code == expected_status, response.text

    with Session(seeded_engine) as session:
        assert session.get(Trial, target_id).model_dump() == before
        assert audit_count(session) == before_audits
