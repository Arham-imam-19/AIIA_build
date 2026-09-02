"""Focused API tests for replacing a trial's complete CTRI registration state."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

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


def body(number: str | None, registration_date: date | None) -> dict:
    return {
        "ctri_number": number,
        "ctri_registration_date": (
            str(registration_date) if registration_date is not None else None
        ),
    }


def patch(client, target_id: int, payload: dict):
    return client.patch(
        f"/api/trials/{target_id}/ctri-registration",
        json=payload,
    )


def set_trial_state(
    seeded_engine,
    *,
    number: str | None = None,
    registration_date: date | None = None,
    start_date: date | None | object = ...,
    activated_at: datetime | None = None,
) -> int:
    with Session(seeded_engine) as session:
        trial = first_trial(session)
        trial.ctri_number = number
        trial.ctri_registration_date = registration_date
        if start_date is not ...:
            trial.start_date = start_date
        trial.activated_at = activated_at
        session.add(trial)
        session.commit()
        assert trial.id is not None
        return trial.id


@pytest.mark.parametrize("role", [UserRole.SPONSOR])
def test_sponsor_and_administrator_can_register_and_number_is_trimmed(
    role_clients, seeded_engine, role
):
    target_id = set_trial_state(seeded_engine)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        registration_date = valid_date(trial)

    response = patch(
        role_clients[role.value],
        target_id,
        body(f"  SYNTHETIC-CTRI-{role.value}  ", registration_date),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "trial_id": target_id,
        "protocol_number": payload["protocol_number"],
        "ctri_number": f"SYNTHETIC-CTRI-{role.value}",
        "ctri_registration_date": str(registration_date),
        "updated_at": payload["updated_at"],
    }

    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.ctri_number == f"SYNTHETIC-CTRI-{role.value}"
        assert trial.ctri_registration_date == registration_date


def test_explicit_null_pair_clears_registration_before_activation(client, seeded_engine):
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-CTRI-TO-CLEAR",
        registration_date=utc_today() - timedelta(days=30),
    )
    with Session(seeded_engine) as session:
        before_audits = audit_count(session)

    response = patch(client, target_id, body(None, None))
    assert response.status_code == 200, response.text
    assert response.json()["ctri_number"] is None
    assert response.json()["ctri_registration_date"] is None
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.ctri_number is None
        assert trial.ctri_registration_date is None
        assert audit_count(session) == before_audits + 1
        entry = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert entry.reason == "Trial CTRI registration cleared."


def test_anonymous_request_returns_401(anonymous_client, seeded_engine):
    target_id = set_trial_state(seeded_engine)
    with Session(seeded_engine) as session:
        before_audits = audit_count(session)
    response = patch(anonymous_client, target_id, body(None, None))
    assert response.status_code == 401
    with Session(seeded_engine) as session:
        assert audit_count(session) == before_audits


@pytest.mark.parametrize(
    "role",
    [
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.REGULATOR,
    ],
)
def test_every_role_without_ctri_write_returns_403_without_side_effects(
    role_clients, seeded_engine, role
):
    target_id = set_trial_state(seeded_engine)
    with Session(seeded_engine) as session:
        before = deepcopy(session.get(Trial, target_id).model_dump())
        before_audits = audit_count(session)

    response = patch(
        role_clients[role.value],
        target_id,
        body("SYNTHETIC-DENIED", utc_today() - timedelta(days=30)),
    )
    assert response.status_code == 403
    assert "ctri:write" in response.json()["detail"]
    with Session(seeded_engine) as session:
        assert session.get(Trial, target_id).model_dump() == before
        assert audit_count(session) == before_audits


def test_missing_trial_uses_existing_404_format_without_audit(client, seeded_engine):
    with Session(seeded_engine) as session:
        before_audits = audit_count(session)
    response = patch(client, 999999, body(None, None))
    assert response.status_code == 404
    assert response.json()["detail"] == "no trial with id 999999"
    with Session(seeded_engine) as session:
        assert audit_count(session) == before_audits


@pytest.mark.parametrize("missing_key", ["ctri_number", "ctri_registration_date"])
def test_both_request_keys_are_required(client, seeded_engine, missing_key):
    target_id = set_trial_state(seeded_engine)
    payload = body(None, None)
    del payload[missing_key]
    assert patch(client, target_id, payload).status_code == 422


def test_unknown_request_field_is_rejected(client, seeded_engine):
    target_id = set_trial_state(seeded_engine)
    payload = body(None, None)
    payload["unexpected"] = "not allowed"
    assert patch(client, target_id, payload).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        body("", utc_today() - timedelta(days=1)),
        body("   ", utc_today() - timedelta(days=1)),
        body("X" * 81, utc_today() - timedelta(days=1)),
        body("SYNTHETIC-NUMBER-ONLY", None),
        body(None, utc_today() - timedelta(days=1)),
        body("SYNTHETIC-FUTURE", utc_today() + timedelta(days=1)),
    ],
)
def test_invalid_shapes_and_values_do_not_mutate_or_audit(
    client, seeded_engine, payload
):
    target_id = set_trial_state(seeded_engine)
    assert_failure_without_side_effects(
        client, seeded_engine, target_id, payload, expected_status=422
    )


def test_registration_date_after_trial_start_is_rejected(client, seeded_engine):
    start = utc_today() - timedelta(days=10)
    target_id = set_trial_state(seeded_engine, start_date=start)
    assert_failure_without_side_effects(
        client,
        seeded_engine,
        target_id,
        body("SYNTHETIC-AFTER-START", start + timedelta(days=1)),
        expected_status=422,
    )


def test_registration_on_trial_start_date_is_accepted(client, seeded_engine):
    start = utc_today() - timedelta(days=10)
    target_id = set_trial_state(seeded_engine, start_date=start)
    response = patch(client, target_id, body("SYNTHETIC-ON-START", start))
    assert response.status_code == 200, response.text
    assert response.json()["ctri_registration_date"] == str(start)


def test_registration_can_be_stored_without_trial_start_date(client, seeded_engine):
    target_id = set_trial_state(seeded_engine, start_date=None)
    registration_date = utc_today() - timedelta(days=1)
    response = patch(
        client, target_id, body("SYNTHETIC-NO-START", registration_date)
    )
    assert response.status_code == 200, response.text
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.start_date is None
        assert trial.ctri_registration_date == registration_date


def test_registration_today_is_allowed_when_start_date_is_null(client, seeded_engine):
    target_id = set_trial_state(seeded_engine, start_date=None)
    response = patch(client, target_id, body("SYNTHETIC-TODAY", utc_today()))
    assert response.status_code == 200, response.text
    assert response.json()["ctri_registration_date"] == str(utc_today())


def test_duplicate_number_owned_by_another_trial_returns_409_without_side_effects(
    client, seeded_engine
):
    duplicate = "SYNTHETIC-CTRI-DUPLICATE"
    with Session(seeded_engine) as session:
        source = first_trial(session)
        other = Trial(
            protocol_number="SYNTHETIC-PROTOCOL-DUPLICATE",
            title="Synthetic duplicate CTRI owner",
            short_title="Synthetic duplicate owner",
            ctri_number=duplicate,
            ctri_registration_date=utc_today() - timedelta(days=5),
            phase=TrialPhase.PHASE_1.value,
            status=TrialStatus.PLANNING.value,
            indication="Synthetic indication",
            intervention="Synthetic intervention",
            design="Synthetic design",
            sponsor_name="Synthetic sponsor",
        )
        source.ctri_number = None
        source.ctri_registration_date = None
        source.activated_at = None
        session.add(source)
        session.add(other)
        session.commit()
        target_id = source.id
        assert target_id is not None

    assert_failure_without_side_effects(
        client,
        seeded_engine,
        target_id,
        body(duplicate, utc_today() - timedelta(days=5)),
        expected_status=409,
    )


def test_reusing_current_trials_own_number_is_an_allowed_noop(client, seeded_engine):
    registration_date = utc_today() - timedelta(days=5)
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-CTRI-OWN",
        registration_date=registration_date,
    )
    response = patch(
        client,
        target_id,
        body("  SYNTHETIC-CTRI-OWN  ", registration_date),
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("clearing", [False, True])
def test_actual_change_or_clearing_after_activation_returns_409(
    client, seeded_engine, clearing
):
    registration_date = utc_today() - timedelta(days=20)
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-ACTIVATED",
        registration_date=registration_date,
        activated_at=utcnow() - timedelta(days=1),
    )
    payload = (
        body(None, None)
        if clearing
        else body("SYNTHETIC-ACTIVATED-CHANGED", registration_date)
    )
    assert_failure_without_side_effects(
        client, seeded_engine, target_id, payload, expected_status=409
    )


def test_identical_noop_after_activation_does_not_update_or_audit(
    client, seeded_engine
):
    registration_date = utc_today() - timedelta(days=20)
    target_id = set_trial_state(
        seeded_engine,
        number="SYNTHETIC-ACTIVATED-NOOP",
        registration_date=registration_date,
        activated_at=utcnow() - timedelta(days=1),
    )
    with Session(seeded_engine) as session:
        before_updated_at = session.get(Trial, target_id).updated_at
        before_audits = audit_count(session)

    response = patch(
        client,
        target_id,
        body("  SYNTHETIC-ACTIVATED-NOOP  ", registration_date),
    )
    assert response.status_code == 200, response.text
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.updated_at == before_updated_at
        assert audit_count(session) == before_audits


def test_successful_change_audits_once_and_preserves_unrelated_trial_fields(
    client, seeded_engine
):
    target_id = set_trial_state(seeded_engine)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        registration_date = valid_date(trial)
        protected = {
            "status": trial.status,
            "activated_at": trial.activated_at,
            "activated_by_user_id": trial.activated_by_user_id,
            "ethics_approval_number": trial.ethics_approval_number,
            "ethics_approval_date": trial.ethics_approval_date,
            "ethics_approval_status": trial.ethics_approval_status,
            "ethics_approval_valid_until": trial.ethics_approval_valid_until,
            "regulatory_approval_number": trial.regulatory_approval_number,
            "regulatory_approval_date": trial.regulatory_approval_date,
            "start_date": trial.start_date,
            "planned_end_date": trial.planned_end_date,
        }
        before_updated_at = trial.updated_at
        before_audits = audit_count(session)

    response = patch(
        client,
        target_id,
        body("SYNTHETIC-CTRI-AUDITED", registration_date),
    )
    assert response.status_code == 200, response.text

    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.updated_at > before_updated_at
        assert audit_count(session) == before_audits + 1
        assert {
            "status": trial.status,
            "activated_at": trial.activated_at,
            "activated_by_user_id": trial.activated_by_user_id,
            "ethics_approval_number": trial.ethics_approval_number,
            "ethics_approval_date": trial.ethics_approval_date,
            "ethics_approval_status": trial.ethics_approval_status,
            "ethics_approval_valid_until": trial.ethics_approval_valid_until,
            "regulatory_approval_number": trial.regulatory_approval_number,
            "regulatory_approval_date": trial.regulatory_approval_date,
            "start_date": trial.start_date,
            "planned_end_date": trial.planned_end_date,
        } == protected
        entry = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert entry.action == AuditAction.UPDATE.value
        assert entry.entity_type == "trials"
        assert entry.entity_id == target_id
        assert entry.entity_label == trial.protocol_number
        assert entry.field_name == "ctri_number"
        assert entry.trial_id == target_id
        assert entry.old_value and "ctri_registration_date" in entry.old_value
        assert entry.new_value and "SYNTHETIC-CTRI-AUDITED" in entry.new_value
        assert entry.reason == "Trial CTRI registration updated."


def assert_failure_without_side_effects(
    client,
    seeded_engine,
    target_id: int,
    payload: dict,
    *,
    expected_status: int,
) -> None:
    with Session(seeded_engine) as session:
        before = deepcopy(session.get(Trial, target_id).model_dump())
        before_audits = audit_count(session)

    response = patch(client, target_id, payload)
    assert response.status_code == expected_status, response.text

    with Session(seeded_engine) as session:
        assert session.get(Trial, target_id).model_dump() == before
        assert audit_count(session) == before_audits
