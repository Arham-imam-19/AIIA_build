"""End-to-end integration test for the full Step 2 / Version 4 Compliance, Privacy & Ethics lifecycle."""

from datetime import date, timedelta
from sqlmodel import Session, select

from app.enums import EthicsApprovalStatus, Sex, StudyArm, SubjectStatus, UserRole
from app.models import Site, Subject, Trial, User
from tests.conftest import client_for, client_for_user


def test_full_compliance_lifecycle_e2e(seeded_engine):
    with Session(seeded_engine) as session:
        trial = session.exec(select(Trial)).first()
        assert trial is not None
        site = session.exec(select(Site).where(Site.trial_id == trial.id)).first()
        assert site is not None
        coordinator = session.exec(
            select(User).where(User.role == UserRole.COORDINATOR.value, User.site_id == site.id)
        ).first()
        assert coordinator is not None
        trial_id = trial.id
        site_id = site.id

    coord_client = client_for_user(seeded_engine, coordinator)
    ethics_client = client_for(seeded_engine, UserRole.ETHICS_COMMITTEE.value)
    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)
    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)

    # 1. Revoke / Set ethics status to PENDING
    res_revoke = ethics_client.patch(
        f"/api/trials/{trial_id}/ethics-approval",
        json={
            "ethics_approval_status": EthicsApprovalStatus.PENDING.value,
            "ethics_approval_number": None,
            "ethics_approval_date": None,
            "ethics_approval_valid_until": None,
        },
    )
    assert res_revoke.status_code == 200
    assert res_revoke.json()["ethics_approval_status"] == EthicsApprovalStatus.PENDING.value

    # 2. Doctor/Coordinator attempts screening -> BLOCKED WITH 409
    screening_payload = {
        "trial_id": trial_id,
        "site_id": site_id,
        "screening_date": date.today().isoformat(),
        "sex": Sex.MALE.value,
        "year_of_birth": 1992,
    }
    res_blocked = coord_client.post("/api/subjects", json=screening_payload)
    assert res_blocked.status_code == 409
    assert "Enrollment Blocked" in res_blocked.json()["detail"]

    # 3. Ethics Committee grants formal approval
    approval_payload = {
        "ethics_approval_status": EthicsApprovalStatus.APPROVED.value,
        "ethics_approval_number": "IEC/AIIA/2026/088",
        "ethics_approval_date": date.today().isoformat(),
        "ethics_approval_valid_until": (date.today() + timedelta(days=365)).isoformat(),
    }
    res_approve = ethics_client.patch(
        f"/api/trials/{trial_id}/ethics-approval",
        json=approval_payload,
    )
    assert res_approve.status_code == 200

    # 4. Doctor/Coordinator screens and enrolls participant -> SUCCEEDS
    res_screen = coord_client.post("/api/subjects", json=screening_payload)
    assert res_screen.status_code == 201
    subj_data = res_screen.json()
    subject_id = subj_data["id"]
    assert subj_data["status"] == SubjectStatus.SCREENING.value

    enroll_payload = {
        "enrollment_date": date.today().isoformat(),
        "randomization_date": date.today().isoformat(),
        "arm": StudyArm.TREATMENT.value,
    }
    res_enroll = coord_client.patch(f"/api/subjects/{subject_id}/enrollment", json=enroll_payload)
    assert res_enroll.status_code == 200
    assert res_enroll.json()["status"] == SubjectStatus.ENROLLED.value

    # 5. Regulator inspects the ALCOA+ Audit Trail
    res_audit = regulator_client.get(f"/api/audit-log?trial_id={trial_id}&limit=10")
    assert res_audit.status_code == 200
    audit_items = res_audit.json()["items"]
    assert len(audit_items) > 0
    # Confirm audit log captured ethics approval and enrollment
    actions = [item["action"] for item in audit_items]
    assert "approve" in actions or "update" in actions
    assert "create" in actions or "update" in actions

    # 6. Data Minimization check: Sponsor views users/e-consent and receives pseudonymized view
    res_users = sponsor_client.get("/api/users?role=patient")
    assert res_users.status_code == 200
    for u in res_users.json()["items"]:
        assert "@***." in u["email"]
        assert "Subject" in u["full_name"] or "De-identified" in u["full_name"]
