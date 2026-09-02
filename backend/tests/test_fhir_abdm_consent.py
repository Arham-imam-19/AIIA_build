"""Tests for HL7 FHIR R4 Consent resource and ABDM Consent Artefact export."""

from sqlmodel import Session, select

from app.enums import UserRole
from app.models import EConsent, Subject, User
from tests.conftest import client_for, client_for_user


def test_fhir_and_abdm_consent_export(seeded_engine):
    with Session(seeded_engine) as session:
        consent = session.exec(select(EConsent)).first()
        assert consent is not None
        subject = session.get(Subject, consent.subject_id)
        assert subject is not None
        patient_user = session.get(User, consent.user_id)
        assert patient_user is not None
        patient_user.subject_id = subject.id
        session.add(patient_user)
        session.commit()
        session.refresh(patient_user)

        subject_id = subject.id
        subject_code = subject.subject_code
        sha256_hash = consent.sha256_hash
        abha_id = consent.abha_id

    patient_client = client_for_user(seeded_engine, patient_user)
    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)

    # 1. Test HL7 FHIR R4 Consent resource endpoint
    fhir_res = patient_client.get(f"/api/econsent/subjects/{subject_id}/fhir")
    assert fhir_res.status_code == 200
    fhir = fhir_res.json()
    assert fhir["resourceType"] == "Consent"
    assert fhir["status"] == "active"
    assert fhir["scope"]["coding"][0]["code"] == "research"
    assert fhir["category"][0]["coding"][0]["code"] == "research"
    assert fhir["patient"]["reference"] == f"Patient/{subject_code}"
    assert "provision" in fhir
    assert fhir["provision"]["purpose"][0]["code"] == "CLINTRL"

    # 2. Test ABDM Consent Artefact endpoint
    abdm_res = patient_client.get(f"/api/econsent/subjects/{subject_id}/abdm-artefact")
    assert abdm_res.status_code == 200
    abdm = abdm_res.json()
    assert "consentDetail" in abdm
    assert abdm["consentDetail"]["schemaVersion"] == "v0.5"
    assert abdm["consentDetail"]["purpose"]["code"] == "CA-01"
    assert abdm["consentDetail"]["purpose"]["text"] == "Clinical Trial Research"
    assert "signature" in abdm
    assert abdm["signature"]["algorithm"] == "SHA256withECDSA"
    assert abdm["signature"]["digest"] == sha256_hash
    assert "21 CFR" in abdm["signature"]["meaning"] or "GCP-ASU" in abdm["signature"]["meaning"]

    # 3. Test DPDP minimization on FHIR / ABDM for oversight roles
    reg_fhir_res = regulator_client.get(f"/api/econsent/subjects/{subject_id}/fhir")
    assert reg_fhir_res.status_code == 200
    reg_fhir = reg_fhir_res.json()
    # ABHA should be masked for regulator
    if abha_id:
        assert "XXXX" in reg_fhir["patient"]["identifier"]["value"]
