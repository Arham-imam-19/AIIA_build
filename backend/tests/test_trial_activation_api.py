"""Focused API tests for the Trial activation transition.

SQLite accepts SQLAlchemy's ``with_for_update()`` query construction but cannot
prove PostgreSQL row-lock concurrency. These tests cover endpoint behavior and
persistence; production lock contention belongs in PostgreSQL integration tests.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta
import json

import pytest
from sqlalchemy import func
from sqlmodel import Session, select

from app.enums import AuditAction, EthicsApprovalStatus, TrialStatus, UserRole
from app.models import AuditLog, Trial
from app.services.trial_compliance import (
    ActivationBlocker,
    ActivationEligibilityResult,
)
from tests.conftest import users_by_role


ROUTE = "/api/trials/{trial_id}/activate"
RESPONSE_FIELDS = {
    "trial_id",
    "protocol_number",
    "current_status",
    "activated_at",
    "activated_by_user_id",
    "updated_at",
}


def first_trial(session: Session) -> Trial:
    trial = session.exec(select(Trial).order_by(Trial.id)).first()
    assert trial is not None
    return trial


def audit_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(AuditLog)).one()


def make_eligible(trial: Trial, status: TrialStatus = TrialStatus.APPROVED) -> None:
    today = date.today()
    trial.protocol_number = trial.protocol_number or "SYNTHETIC-ACTIVATION-001"
    trial.title = trial.title or "Synthetic activation trial"
    trial.phase = trial.phase or "phase_3"
    trial.intervention = trial.intervention or "Synthetic intervention"
    trial.sponsor_name = trial.sponsor_name or "Synthetic sponsor"
    trial.target_enrollment = 100
    trial.start_date = today + timedelta(days=1)
    trial.planned_end_date = today + timedelta(days=365)
    trial.ethics_approval_status = EthicsApprovalStatus.APPROVED.value
    trial.ethics_approval_number = "SYNTHETIC-IEC-ACTIVATION"
    trial.ethics_approval_date = today - timedelta(days=10)
    trial.ethics_approval_valid_until = today + timedelta(days=365)
    trial.ctri_number = trial.ctri_number or "SYNTHETIC-CTRI-ACTIVATION"
    trial.ctri_registration_date = today - timedelta(days=9)
    trial.regulatory_approval_number = "SYNTHETIC-REG-ACTIVATION"
    trial.regulatory_approval_date = today - timedelta(days=8)
    trial.status = status.value
    trial.activated_at = None
    trial.activated_by_user_id = None


def prepare_trial(seeded_engine, status: TrialStatus = TrialStatus.APPROVED) -> int:
    with Session(seeded_engine) as session:
        trial = first_trial(session)
        make_eligible(trial, status)
        session.add(trial)
        session.commit()
        assert trial.id is not None
        return trial.id


def post(client, trial_id: int):
    return client.post(ROUTE.format(trial_id=trial_id))


def snapshot(seeded_engine, trial_id: int) -> tuple[dict, int]:
    with Session(seeded_engine) as session:
        return deepcopy(session.get(Trial, trial_id).model_dump()), audit_count(session)


@pytest.mark.parametrize("role", [UserRole.SPONSOR, UserRole.ADMIN])
def test_authorized_role_activates_and_persists_exact_response(
    role_clients, seeded_engine, role
):
    trial_id = prepare_trial(seeded_engine)
    actor = users_by_role(seeded_engine, role.value)[0]

    response = post(role_clients[role.value], trial_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert body["trial_id"] == trial_id
    assert body["current_status"] == TrialStatus.RECRUITING.value
    assert body["activated_by_user_id"] == actor.id
    assert body["activated_at"] == body["updated_at"]
    with Session(seeded_engine) as session:
        trial = session.get(Trial, trial_id)
        assert trial.status == TrialStatus.RECRUITING.value
        assert trial.activated_by_user_id == actor.id
        assert trial.activated_at == trial.updated_at
        assert trial.activated_at.isoformat() == body["activated_at"]


def test_success_creates_exactly_one_complete_activation_audit(
    role_clients, seeded_engine
):
    trial_id = prepare_trial(seeded_engine, TrialStatus.PENDING_ETHICS)
    actor = users_by_role(seeded_engine, UserRole.SPONSOR.value)[0]
    with Session(seeded_engine) as session:
        before_audits = audit_count(session)
        protocol_number = session.get(Trial, trial_id).protocol_number

    response = post(role_clients[UserRole.SPONSOR.value], trial_id)
    assert response.status_code == 200, response.text

    with Session(seeded_engine) as session:
        assert audit_count(session) == before_audits + 1
        entry = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert entry.action == AuditAction.UPDATE.value
        assert entry.entity_type == "trials"
        assert entry.entity_id == trial_id
        assert entry.entity_label == protocol_number
        assert entry.field_name == "activation"
        assert entry.trial_id == trial_id
        assert entry.user_id == actor.id
        assert entry.user_email == actor.email
        assert entry.user_role == actor.role
        assert entry.reason == "Trial activated from pending_ethics to recruiting."
        assert entry.old_value == json.dumps(
            {
                "status": TrialStatus.PENDING_ETHICS.value,
                "activated_at": None,
                "activated_by_user_id": None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        assert entry.new_value == json.dumps(
            {
                "status": TrialStatus.RECRUITING.value,
                "activated_at": response.json()["activated_at"],
                "activated_by_user_id": actor.id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def test_success_preserves_unrelated_trial_fields(role_clients, seeded_engine):
    trial_id = prepare_trial(seeded_engine)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, trial_id)
        protected = {
            key: getattr(trial, key)
            for key in (
                "ethics_approval_status",
                "ethics_approval_number",
                "ethics_approval_date",
                "ethics_approval_valid_until",
                "ctri_number",
                "ctri_registration_date",
                "regulatory_approval_number",
                "regulatory_approval_date",
                "start_date",
                "planned_end_date",
                "target_enrollment",
                "title",
                "intervention",
            )
        }

    assert post(role_clients[UserRole.SPONSOR.value], trial_id).status_code == 200
    with Session(seeded_engine) as session:
        trial = session.get(Trial, trial_id)
        assert {key: getattr(trial, key) for key in protected} == protected


def test_anonymous_request_has_no_side_effects(anonymous_client, seeded_engine):
    trial_id = prepare_trial(seeded_engine)
    before = snapshot(seeded_engine, trial_id)
    response = post(anonymous_client, trial_id)
    assert response.status_code == 401
    assert snapshot(seeded_engine, trial_id) == before


@pytest.mark.parametrize(
    "role",
    [
        UserRole.REGULATOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
    ],
)
def test_unauthorized_roles_have_no_side_effects(
    role_clients, seeded_engine, role
):
    trial_id = prepare_trial(seeded_engine)
    before = snapshot(seeded_engine, trial_id)
    response = post(role_clients[role.value], trial_id)
    assert response.status_code == 403
    assert "activation:write" in response.json()["detail"]
    assert snapshot(seeded_engine, trial_id) == before


def test_missing_trial_uses_existing_404_format(role_clients):
    response = post(role_clients[UserRole.SPONSOR.value], 999999)
    assert response.status_code == 404
    assert response.json()["detail"] == "no trial with id 999999"


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        ({"title": ""}, "PROTOCOL_INCOMPLETE"),
        ({"ethics_approval_status": EthicsApprovalStatus.PENDING.value}, "ETHICS_NOT_APPROVED"),
        ({"ctri_number": None}, "CTRI_MISSING"),
        ({"regulatory_approval_number": None}, "REGULATORY_APPROVAL_MISSING"),
        ({"status": TrialStatus.COMPLETED.value}, "TRIAL_STATUS_NOT_ACTIVATABLE"),
    ],
)
def test_representative_compliance_blockers_are_returned_authoritatively(
    role_clients, seeded_engine, change, expected_code
):
    trial_id = prepare_trial(seeded_engine)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, trial_id)
        for key, value in change.items():
            setattr(trial, key, value)
        session.add(trial)
        session.commit()
    before = snapshot(seeded_engine, trial_id)

    response = post(role_clients[UserRole.SPONSOR.value], trial_id)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["message"] == "trial is not eligible for activation"
    blockers = {item["code"]: item["message"] for item in detail["blockers"]}
    assert expected_code in blockers
    assert blockers[expected_code]
    assert snapshot(seeded_engine, trial_id) == before


def test_router_uses_existing_compliance_service(
    role_clients, seeded_engine, monkeypatch
):
    from app.routers import trials as trials_router

    trial_id = prepare_trial(seeded_engine)
    sentinel = ActivationBlocker("SERVICE_SENTINEL", "service supplied this blocker")
    calls = []

    def fake_checker(trial, as_of=None):
        calls.append((trial.id, as_of))
        return ActivationEligibilityResult(False, (), (sentinel,))

    monkeypatch.setattr(
        trials_router.trial_compliance, "check_activation_eligibility", fake_checker
    )
    response = post(role_clients[UserRole.SPONSOR.value], trial_id)
    assert calls == [(trial_id, None)]
    assert response.status_code == 409
    assert response.json()["detail"]["blockers"] == [asdict(sentinel)]


def test_coherent_repeat_is_idempotent_without_service_audit_or_commit(
    role_clients, seeded_engine, monkeypatch
):
    from app.routers import trials as trials_router

    trial_id = prepare_trial(seeded_engine)
    client = role_clients[UserRole.SPONSOR.value]
    first = post(client, trial_id)
    assert first.status_code == 200
    before = snapshot(seeded_engine, trial_id)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("coherent repeat must not call this")

    monkeypatch.setattr(trials_router.trial_compliance, "check_activation_eligibility", unexpected)
    monkeypatch.setattr(trials_router.audit, "record", unexpected)
    monkeypatch.setattr(Session, "commit", unexpected)
    repeated = post(client, trial_id)

    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    assert snapshot(seeded_engine, trial_id) == before


@pytest.mark.parametrize(
    ("status", "has_time", "has_actor"),
    [
        (TrialStatus.RECRUITING, False, True),
        (TrialStatus.RECRUITING, True, False),
        (TrialStatus.RECRUITING, False, False),
        (TrialStatus.APPROVED, True, True),
        (TrialStatus.APPROVED, True, False),
        (TrialStatus.APPROVED, False, True),
    ],
)
def test_inconsistent_activation_states_return_409_without_side_effects(
    role_clients, seeded_engine, status, has_time, has_actor
):
    from app.models.base import utcnow

    trial_id = prepare_trial(seeded_engine, status)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, trial_id)
        trial.activated_at = utcnow() if has_time else None
        trial.activated_by_user_id = (
            users_by_role(seeded_engine, UserRole.SPONSOR.value)[0].id
            if has_actor
            else None
        )
        session.add(trial)
        session.commit()
    before = snapshot(seeded_engine, trial_id)

    response = post(role_clients[UserRole.SPONSOR.value], trial_id)
    assert response.status_code == 409
    assert response.json()["detail"] == "trial activation state is inconsistent"
    assert snapshot(seeded_engine, trial_id) == before


def test_audit_helper_failure_rolls_back_trial(
    role_clients, seeded_engine, monkeypatch
):
    from app.routers import trials as trials_router

    trial_id = prepare_trial(seeded_engine)
    before = snapshot(seeded_engine, trial_id)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(trials_router.audit, "record", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        post(role_clients[UserRole.SPONSOR.value], trial_id)
    assert snapshot(seeded_engine, trial_id) == before


def test_commit_failure_calls_rollback_and_persists_nothing(
    role_clients, seeded_engine, monkeypatch
):
    trial_id = prepare_trial(seeded_engine)
    before = snapshot(seeded_engine, trial_id)
    original_rollback = Session.rollback
    rollbacks = []

    def fail_commit(_session):
        raise RuntimeError("synthetic commit failure")

    def track_rollback(session):
        rollbacks.append(True)
        return original_rollback(session)

    monkeypatch.setattr(Session, "commit", fail_commit)
    monkeypatch.setattr(Session, "rollback", track_rollback)
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        post(role_clients[UserRole.SPONSOR.value], trial_id)
    assert rollbacks == [True]
    assert snapshot(seeded_engine, trial_id) == before
