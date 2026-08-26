"""Focused API tests for writing a trial's complete ethics-approval state."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func
from sqlmodel import Session, select

from app.enums import AuditAction, EthicsApprovalStatus, UserRole
from app.models import AuditLog, Trial


def first_trial(session: Session) -> Trial:
    trial = session.exec(select(Trial).order_by(Trial.id)).first()
    assert trial is not None
    return trial


def trial_id(seeded_engine) -> int:
    with Session(seeded_engine) as session:
        found = first_trial(session)
        assert found.id is not None
        return found.id


def audit_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(AuditLog)).one()


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def payload(
    status: EthicsApprovalStatus,
    *,
    number: str | None = None,
    approval_date: date | None = None,
    valid_until: date | None = None,
) -> dict:
    return {
        "ethics_approval_status": status.value,
        "ethics_approval_number": number,
        "ethics_approval_date": str(approval_date) if approval_date else None,
        "ethics_approval_valid_until": str(valid_until) if valid_until else None,
    }


def approved_payload() -> dict:
    today = utc_today()
    return payload(
        EthicsApprovalStatus.APPROVED,
        number="  SYNTHETIC-IEC-PHASE4B-001  ",
        approval_date=today - timedelta(days=10),
        valid_until=today + timedelta(days=365),
    )


def patch(client, seeded_engine, body: dict):
    return client.patch(
        f"/api/trials/{trial_id(seeded_engine)}/ethics-approval", json=body
    )


def test_successful_approved_update_persists_audits_and_preserves_other_fields(
    client, seeded_engine
):
    target_id = trial_id(seeded_engine)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        protected = {
            "status": trial.status,
            "activated_at": trial.activated_at,
            "activated_by_user_id": trial.activated_by_user_id,
            "ctri_number": trial.ctri_number,
            "ctri_registration_date": trial.ctri_registration_date,
            "regulatory_approval_number": trial.regulatory_approval_number,
            "regulatory_approval_date": trial.regulatory_approval_date,
        }
        before_updated_at = trial.updated_at
        before_audits = audit_count(session)

    response = client.patch(
        f"/api/trials/{target_id}/ethics-approval", json=approved_payload()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trial_id"] == target_id
    assert body["ethics_approval_status"] == EthicsApprovalStatus.APPROVED.value
    assert body["ethics_approval_number"] == "SYNTHETIC-IEC-PHASE4B-001"

    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.ethics_approval_status == EthicsApprovalStatus.APPROVED.value
        assert trial.ethics_approval_number == "SYNTHETIC-IEC-PHASE4B-001"
        assert str(trial.ethics_approval_date) == body["ethics_approval_date"]
        assert str(trial.ethics_approval_valid_until) == body[
            "ethics_approval_valid_until"
        ]
        assert trial.updated_at > before_updated_at
        assert {
            "status": trial.status,
            "activated_at": trial.activated_at,
            "activated_by_user_id": trial.activated_by_user_id,
            "ctri_number": trial.ctri_number,
            "ctri_registration_date": trial.ctri_registration_date,
            "regulatory_approval_number": trial.regulatory_approval_number,
            "regulatory_approval_date": trial.regulatory_approval_date,
        } == protected
        assert audit_count(session) == before_audits + 1
        entry = session.exec(
            select(AuditLog).order_by(AuditLog.id.desc())
        ).first()
        assert entry.action == AuditAction.APPROVE.value
        assert entry.entity_type == "trials"
        assert entry.entity_id == target_id
        assert entry.trial_id == target_id
        assert entry.field_name == "ethics_approval"
        assert entry.old_value and entry.new_value
        assert "approved" in entry.new_value


def test_identical_normalized_request_is_noop_without_commit(
    client, seeded_engine, monkeypatch
):
    target_id = trial_id(seeded_engine)
    today = utc_today()
    approval_date = today - timedelta(days=10)
    valid_until = today + timedelta(days=365)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        trial.ethics_approval_status = EthicsApprovalStatus.APPROVED.value
        trial.ethics_approval_number = "SYNTHETIC-IEC-NOOP"
        trial.ethics_approval_date = approval_date
        trial.ethics_approval_valid_until = valid_until
        session.add(trial)
        session.commit()
        protocol_number = trial.protocol_number
        before_updated_at = trial.updated_at
        before_audits = audit_count(session)

    def unexpected_commit(_session):
        raise AssertionError("identical ethics request must not commit")

    monkeypatch.setattr(Session, "commit", unexpected_commit)
    response = client.patch(
        f"/api/trials/{target_id}/ethics-approval",
        json=payload(
            EthicsApprovalStatus.APPROVED,
            number="  SYNTHETIC-IEC-NOOP  ",
            approval_date=approval_date,
            valid_until=valid_until,
        ),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "trial_id": target_id,
        "protocol_number": protocol_number,
        "ethics_approval_status": EthicsApprovalStatus.APPROVED.value,
        "ethics_approval_number": "SYNTHETIC-IEC-NOOP",
        "ethics_approval_date": str(approval_date),
        "ethics_approval_valid_until": str(valid_until),
        "updated_at": before_updated_at.isoformat(),
    }
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target_id)
        assert trial.updated_at == before_updated_at
        assert audit_count(session) == before_audits


@pytest.mark.parametrize(
    ("status", "number", "approval_offset", "validity_offset", "action"),
    [
        (EthicsApprovalStatus.PENDING, None, None, None, AuditAction.UPDATE),
        (EthicsApprovalStatus.REJECTED, None, None, None, AuditAction.REJECT),
        (EthicsApprovalStatus.NOT_SUBMITTED, None, None, None, AuditAction.UPDATE),
        (EthicsApprovalStatus.EXPIRED, "SYNTHETIC-OLD-IEC", -30, -1, AuditAction.UPDATE),
    ],
)
def test_valid_target_states_are_permitted_and_audited_once(
    client,
    seeded_engine,
    status,
    number,
    approval_offset,
    validity_offset,
    action,
):
    today = utc_today()
    body = payload(
        status,
        number=number,
        approval_date=(today + timedelta(days=approval_offset))
        if approval_offset is not None
        else None,
        valid_until=(today + timedelta(days=validity_offset))
        if validity_offset is not None
        else None,
    )
    with Session(seeded_engine) as session:
        before_audits = audit_count(session)

    response = patch(client, seeded_engine, body)
    assert response.status_code == 200, response.text
    assert response.json()["ethics_approval_status"] == status.value

    with Session(seeded_engine) as session:
        trial = session.get(Trial, trial_id(seeded_engine))
        assert trial.ethics_approval_status == status.value
        assert trial.ethics_approval_number == number
        assert audit_count(session) == before_audits + 1
        entry = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert entry.action == action.value


def test_anonymous_request_returns_401(anonymous_client, seeded_engine):
    response = patch(anonymous_client, seeded_engine, approved_payload())
    assert response.status_code == 401


def test_role_without_ethics_write_returns_403(role_clients, seeded_engine):
    response = patch(
        role_clients[UserRole.REGULATOR.value], seeded_engine, approved_payload()
    )
    assert response.status_code == 403
    assert "ethics:write" in response.json()["detail"]


@pytest.mark.parametrize("role", [UserRole.ETHICS_COMMITTEE, UserRole.ADMIN])
def test_ethics_committee_and_admin_are_permitted(role_clients, seeded_engine, role):
    response = patch(
        role_clients[role.value],
        seeded_engine,
        payload(EthicsApprovalStatus.PENDING),
    )
    assert response.status_code == 200, response.text


def test_missing_trial_uses_existing_404_format(client):
    response = client.patch(
        "/api/trials/999999/ethics-approval", json=approved_payload()
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "no trial with id 999999"


def test_unknown_status_is_rejected(client, seeded_engine):
    body = approved_payload()
    body["ethics_approval_status"] = "unknown"
    assert patch(client, seeded_engine, body).status_code == 422


def test_missing_required_request_key_is_rejected(client, seeded_engine):
    body = approved_payload()
    del body["ethics_approval_number"]
    assert patch(client, seeded_engine, body).status_code == 422


def test_unknown_request_field_is_rejected(client, seeded_engine):
    body = approved_payload()
    body["unexpected"] = "not allowed"
    assert patch(client, seeded_engine, body).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        payload(
            EthicsApprovalStatus.APPROVED,
            number="   ",
            approval_date=utc_today() - timedelta(days=1),
            valid_until=utc_today() + timedelta(days=1),
        ),
        payload(
            EthicsApprovalStatus.APPROVED,
            number=None,
            approval_date=utc_today() - timedelta(days=1),
            valid_until=utc_today() + timedelta(days=1),
        ),
        payload(
            EthicsApprovalStatus.APPROVED,
            number="SYNTHETIC-IEC",
            approval_date=None,
            valid_until=utc_today() + timedelta(days=1),
        ),
        payload(
            EthicsApprovalStatus.APPROVED,
            number="SYNTHETIC-IEC",
            approval_date=utc_today() - timedelta(days=1),
            valid_until=None,
        ),
        payload(
            EthicsApprovalStatus.APPROVED,
            number="SYNTHETIC-IEC",
            approval_date=utc_today() + timedelta(days=1),
            valid_until=utc_today() + timedelta(days=2),
        ),
        payload(
            EthicsApprovalStatus.APPROVED,
            number="SYNTHETIC-IEC",
            approval_date=utc_today(),
            valid_until=utc_today() - timedelta(days=1),
        ),
        payload(
            EthicsApprovalStatus.APPROVED,
            number="SYNTHETIC-IEC",
            approval_date=utc_today() - timedelta(days=2),
            valid_until=utc_today() - timedelta(days=1),
        ),
    ],
)
def test_invalid_approved_states_do_not_mutate_or_audit(
    client, seeded_engine, body
):
    assert_failed_without_side_effects(client, seeded_engine, body)


@pytest.mark.parametrize(
    "body",
    [
        payload(EthicsApprovalStatus.EXPIRED),
        payload(
            EthicsApprovalStatus.EXPIRED,
            number="SYNTHETIC-IEC",
            approval_date=utc_today() - timedelta(days=1),
            valid_until=utc_today(),
        ),
        payload(
            EthicsApprovalStatus.EXPIRED,
            number="SYNTHETIC-IEC",
            approval_date=utc_today() - timedelta(days=1),
            valid_until=utc_today() + timedelta(days=1),
        ),
        payload(
            EthicsApprovalStatus.EXPIRED,
            number="SYNTHETIC-IEC",
            approval_date=utc_today() - timedelta(days=1),
            valid_until=utc_today() - timedelta(days=2),
        ),
    ],
)
def test_invalid_expired_states_do_not_mutate_or_audit(
    client, seeded_engine, body
):
    assert_failed_without_side_effects(client, seeded_engine, body)


@pytest.mark.parametrize(
    "status",
    [
        EthicsApprovalStatus.PENDING,
        EthicsApprovalStatus.REJECTED,
        EthicsApprovalStatus.NOT_SUBMITTED,
    ],
)
def test_non_approval_statuses_reject_approval_details(
    client, seeded_engine, status
):
    body = payload(status, number="CONTRADICTORY")
    assert_failed_without_side_effects(client, seeded_engine, body)


def assert_failed_without_side_effects(client, seeded_engine, body: dict) -> None:
    target_id = trial_id(seeded_engine)
    with Session(seeded_engine) as session:
        before = deepcopy(session.get(Trial, target_id).model_dump())
        before_audits = audit_count(session)

    response = client.patch(
        f"/api/trials/{target_id}/ethics-approval", json=body
    )
    assert response.status_code == 422, response.text

    with Session(seeded_engine) as session:
        assert session.get(Trial, target_id).model_dump() == before
        assert audit_count(session) == before_audits
