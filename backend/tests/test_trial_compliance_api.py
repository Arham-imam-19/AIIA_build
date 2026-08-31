"""Focused API tests for the read-only trial compliance endpoint."""

from copy import deepcopy
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.enums import EthicsApprovalStatus, TrialStatus, UserRole
from app.models import AuditLog, Trial
from app.services.trial_compliance import (
    ActivationEligibilityResult,
    ComplianceCheck,
)


def first_trial(session: Session) -> Trial:
    trial = session.exec(select(Trial).order_by(Trial.id)).first()
    assert trial is not None
    return trial


def audit_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(AuditLog)).one()


def make_compliant(trial: Trial) -> None:
    trial.protocol_number = trial.protocol_number or "AIIA-TEST-2026-01"
    trial.title = trial.title or "Synthetic compliant trial"
    trial.phase = trial.phase or "phase_3"
    trial.intervention = trial.intervention or "Synthetic study intervention"
    trial.sponsor_name = trial.sponsor_name or "Synthetic sponsor"
    trial.target_enrollment = 100
    trial.start_date = date(2026, 1, 1)
    trial.planned_end_date = date(2027, 1, 1)
    trial.ethics_approval_status = EthicsApprovalStatus.APPROVED.value
    trial.ethics_approval_number = "SYNTHETIC-IEC-001"
    trial.ethics_approval_date = date(2025, 10, 1)
    trial.ethics_approval_valid_until = date(2099, 12, 31)
    trial.ctri_number = trial.ctri_number or "CTRI/2025/01/SYNTHETIC"
    trial.ctri_registration_date = date(2025, 11, 1)
    trial.regulatory_approval_number = "SYNTHETIC-REG-001"
    trial.regulatory_approval_date = date(2025, 12, 1)
    trial.status = TrialStatus.APPROVED.value


def test_authorized_response_has_checker_shape(client, seeded_engine):
    with Session(seeded_engine) as session:
        trial_id = first_trial(session).id

    response = client.get(f"/api/trials/{trial_id}/compliance-status")
    assert response.status_code == 200
    body = response.json()
    assert body["trial_id"] == trial_id
    assert {
        "trial_id",
        "current_status",
        "checks",
        "eligibility",
        "blockers",
    } <= body.keys()
    assert isinstance(body["eligibility"], bool)
    assert "eligible_for_activation" not in body
    assert isinstance(body["checks"], list)
    assert isinstance(body["blockers"], list)


def test_missing_trial_returns_404(client):
    response = client.get("/api/trials/999999/compliance-status")
    assert response.status_code == 404
    assert response.json()["detail"] == "no trial with id 999999"


def test_anonymous_request_returns_401(anonymous_client, seeded_engine):
    with Session(seeded_engine) as session:
        trial_id = first_trial(session).id
    assert anonymous_client.get(
        f"/api/trials/{trial_id}/compliance-status"
    ).status_code == 401


def test_role_without_compliance_read_returns_403(role_clients, seeded_engine):
    with Session(seeded_engine) as session:
        trial_id = first_trial(session).id
    response = role_clients[UserRole.COORDINATOR.value].get(
        f"/api/trials/{trial_id}/compliance-status"
    )
    assert response.status_code == 403
    assert "compliance:read" in response.json()["detail"]


def test_expired_ethics_approval_is_an_activation_blocker(client, seeded_engine):
    with Session(seeded_engine) as session:
        trial = first_trial(session)
        trial.ethics_approval_valid_until = date(2000, 1, 1)
        session.add(trial)
        session.commit()
        trial_id = trial.id

    body = client.get(f"/api/trials/{trial_id}/compliance-status").json()
    assert "ETHICS_APPROVAL_EXPIRED" in {
        blocker["code"] for blocker in body["blockers"]
    }


def test_fully_compliant_trial_is_eligible(client, seeded_engine):
    with Session(seeded_engine) as session:
        trial = first_trial(session)
        make_compliant(trial)
        session.add(trial)
        session.commit()
        trial_id = trial.id

    body = client.get(f"/api/trials/{trial_id}/compliance-status").json()
    assert body["eligibility"] is True
    assert body["blockers"] == []


def test_endpoint_does_not_modify_trial_or_add_audit_log(client, seeded_engine):
    with Session(seeded_engine) as session:
        trial = first_trial(session)
        before = deepcopy(trial.model_dump())
        before_audits = audit_count(session)
        trial_id = trial.id

    assert client.get(f"/api/trials/{trial_id}/compliance-status").status_code == 200

    with Session(seeded_engine) as session:
        assert session.get(Trial, trial_id).model_dump() == before
        assert audit_count(session) == before_audits


def test_endpoint_uses_existing_compliance_service(
    client, seeded_engine, monkeypatch
):
    from app.routers import trials as trials_router

    sentinel = ActivationEligibilityResult(
        eligible_for_activation=False,
        checks=(ComplianceCheck("SERVICE_SENTINEL", True, "service was called"),),
        blockers=(),
    )
    calls = []

    def fake_checker(trial, as_of=None):
        calls.append((trial.id, as_of))
        return sentinel

    monkeypatch.setattr(
        trials_router.trial_compliance, "check_activation_eligibility", fake_checker
    )
    with Session(seeded_engine) as session:
        trial_id = first_trial(session).id

    body = client.get(f"/api/trials/{trial_id}/compliance-status").json()
    assert calls == [(trial_id, None)]
    assert body["checks"][0]["code"] == "SERVICE_SENTINEL"
