"""Tests for Prospective CTRI Registration Sequence Gate under NDCT Rules 2019."""

from datetime import date, timedelta
from sqlmodel import Session, select

from app.enums import EthicsApprovalStatus, Sex, SubjectStatus, UserRole
from app.models import Site, Trial, User
from tests.conftest import client_for_user


def test_ctri_prospective_registration_gate(seeded_engine):
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
        original_ctri = trial.ctri_number
        original_ctri_date = trial.ctri_registration_date

    coord_client = client_for_user(seeded_engine, coordinator)

    screening_payload = {
        "trial_id": trial_id,
        "site_id": site_id,
        "screening_date": date.today().isoformat(),
        "sex": Sex.FEMALE.value,
        "year_of_birth": 1995,
    }

    # 1. Remove CTRI number to simulate un-registered trial
    with Session(seeded_engine) as session:
        t = session.get(Trial, trial_id)
        t.ctri_number = None
        session.add(t)
        session.commit()

    # Attempt screening -> MUST BE BLOCKED (409)
    res_blocked_no_ctri = coord_client.post("/api/subjects", json=screening_payload)
    assert res_blocked_no_ctri.status_code == 409
    assert "Prospective CTRI registration number is required" in res_blocked_no_ctri.json()["detail"]

    # 2. Set CTRI registration date in the future -> MUST BE BLOCKED (409)
    with Session(seeded_engine) as session:
        t = session.get(Trial, trial_id)
        t.ctri_number = "CTRI/2026/09/009999"
        t.ctri_registration_date = date.today() + timedelta(days=10)
        session.add(t)
        session.commit()

    res_blocked_future_ctri = coord_client.post("/api/subjects", json=screening_payload)
    assert res_blocked_future_ctri.status_code == 409
    assert "is in the future" in res_blocked_future_ctri.json()["detail"]

    # 3. Restore valid prospective CTRI registration -> MUST SUCCEED (201)
    with Session(seeded_engine) as session:
        t = session.get(Trial, trial_id)
        t.ctri_number = original_ctri or "CTRI/2026/01/008892"
        t.ctri_registration_date = original_ctri_date or (date.today() - timedelta(days=30))
        t.ethics_approval_status = EthicsApprovalStatus.APPROVED.value
        t.ethics_approval_number = "IEC/AIIA/2026/001"
        t.ethics_approval_date = date.today() - timedelta(days=40)
        t.ethics_approval_valid_until = date.today() + timedelta(days=365)
        session.add(t)
        session.commit()

    res_ok = coord_client.post("/api/subjects", json=screening_payload)
    assert res_ok.status_code == 201
    assert res_ok.json()["status"] == SubjectStatus.SCREENING.value
