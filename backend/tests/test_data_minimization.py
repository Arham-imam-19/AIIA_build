"""Tests for DPDP Act 2023 Data Minimization & Privacy across roles."""

from sqlmodel import Session, select

from app.enums import UserRole
from app.models import EConsent, Subject, User
from app.services import privacy
from tests.conftest import client_for, client_for_user


def test_privacy_masking_unit():
    assert privacy.mask_patient_name("Rahul Sharma", "01-014") == "Subject 01-014"
    assert privacy.mask_phone("+91 9876543210") == "+91 XXXXX-XX210"
    assert privacy.mask_abha_id("14-9988-7766-5544") == "14-XXXX-XXXX-5544"
    assert privacy.mask_email("patient.01.014@demo.aiia-ctms.in") == "p***@***.in"


def test_econsent_data_minimization_across_roles(seeded_engine):
    with Session(seeded_engine) as session:
        consent = session.exec(select(EConsent)).first()
        assert consent is not None
        subject = session.get(Subject, consent.subject_id)
        assert subject is not None
        pi_user = session.exec(
            select(User).where(User.role == UserRole.PRINCIPAL_INVESTIGATOR.value, User.site_id == consent.site_id)
        ).first()
        assert pi_user is not None

    # 1. Site Coordinator / PI sees full signer name
    pi_client = client_for_user(seeded_engine, pi_user)
    res_pi = pi_client.get(f"/api/econsent/subjects/{consent.subject_id}")
    assert res_pi.status_code == 200
    pi_data = res_pi.json()
    assert pi_data["signer_name"] == consent.signer_name
    if consent.abha_id:
        assert pi_data["abha_id"] == consent.abha_id

    # 2. Sponsor / Regulator / Global Admin sees masked signer name and masked ABHA ID
    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)
    res_sp = sponsor_client.get(f"/api/econsent/subjects/{consent.subject_id}")
    assert res_sp.status_code == 200
    sp_data = res_sp.json()
    assert sp_data["signer_name"] == f"Subject {subject.subject_code}"
    if consent.abha_id:
        assert "XXXX" in sp_data["abha_id"]


def test_users_list_data_minimization(seeded_engine):
    with Session(seeded_engine) as session:
        patient_user = session.exec(select(User).where(User.role == UserRole.PATIENT.value)).first()
        assert patient_user is not None

    # Sponsor listing users
    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)
    res = sponsor_client.get("/api/users?role=patient")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) > 0
    p_item = next(u for u in data["items"] if u["id"] == patient_user.id)
    # Check that email and full_name are masked
    assert "@***." in p_item["email"]
    assert "Subject" in p_item["full_name"] or "De-identified" in p_item["full_name"]
