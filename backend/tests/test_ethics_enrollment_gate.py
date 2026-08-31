"""Tests for Institutional Ethics Committee (IEC) State Machine & Enrollment Blockers."""

from datetime import date, timedelta
from sqlmodel import Session, select

from app.enums import EthicsApprovalStatus, Sex, SubjectStatus, UserRole
from app.models import Site, Trial, User
from tests.conftest import client_for, client_for_user


def test_ethics_approval_hard_gate(seeded_engine):
    with Session(seeded_engine) as session:
        trial = session.exec(select(Trial)).first()
        assert trial is not None
        site = session.exec(select(Site).where(Site.trial_id == trial.id)).first()
        assert site is not None
        coordinator = session.exec(
            select(User).where(User.role == UserRole.COORDINATOR.value, User.site_id == site.id)
        ).first()
        assert coordinator is not None

        # Extract values while session is active
        trial_id = trial.id
        site_id = site.id
        coord_client = client_for_user(seeded_engine, coordinator)

        # 1. Temporarily revoke/expire trial ethics approval
        trial.ethics_approval_status = EthicsApprovalStatus.PENDING.value
        session.add(trial)
        session.commit()

    ethics_client = client_for(seeded_engine, UserRole.ETHICS_COMMITTEE.value)

    # 2. Coordinator attempts to create screening subject -> MUST BE BLOCKED (409)
    screening_payload = {
        "trial_id": trial_id,
        "site_id": site_id,
        "screening_date": date.today().isoformat(),
        "sex": Sex.MALE.value,
        "year_of_birth": 1990,
    }
    res_blocked = coord_client.post("/api/subjects", json=screening_payload)
    assert res_blocked.status_code == 409
    assert "Enrollment Blocked" in res_blocked.json()["detail"]
    assert "Institutional Ethics Committee (IEC) approval is required" in res_blocked.json()["detail"]

    # 3. Ethics Committee Member logs in and grants formal approval
    approval_payload = {
        "ethics_approval_status": EthicsApprovalStatus.APPROVED.value,
        "ethics_approval_number": "IEC/AIIA/2026/099",
        "ethics_approval_date": (date.today() - timedelta(days=5)).isoformat(),
        "ethics_approval_valid_until": (date.today() + timedelta(days=365)).isoformat(),
    }
    res_approve = ethics_client.patch(
        f"/api/trials/{trial_id}/ethics-approval",
        json=approval_payload,
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["ethics_approval_status"] == EthicsApprovalStatus.APPROVED.value

    # 4. Now Coordinator attempts to create screening subject -> MUST SUCCEED (201)
    res_ok = coord_client.post("/api/subjects", json=screening_payload)
    assert res_ok.status_code == 201
    created = res_ok.json()
    assert created["status"] == SubjectStatus.SCREENING.value
