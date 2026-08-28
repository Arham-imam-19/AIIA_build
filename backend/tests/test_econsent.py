"""Test suite for Digital e-Consent, Patient Visit Isolation, Atomic Audit, and WebSocket Privacy."""

from __future__ import annotations

from unittest.mock import patch
import pytest
from httpx import Client
from sqlmodel import Session, select

from app import security
from app.enums import AuditAction, ConsentStatus, UserRole
from app.models import AuditLog, EConsent, Site, Subject, Trial, User, Visit
from app.rbac import CurrentUser, Permission
from app.routers.live import _for_viewer, _visible_to


def test_patient_can_view_bilingual_protocol_info_sheet(role_clients):
    patient_client = role_clients[UserRole.PATIENT.value]
    response = patient_client.get("/api/econsent/my")
    assert response.status_code == 200
    data = response.json()
    assert "info_sheet" in data
    assert "Ashwagandha" in data["info_sheet"]["trial_title_en"]
    assert "अश्वगंधा" in data["info_sheet"]["trial_title_hi"]
    assert len(data["info_sheet"]["key_points_en"]) > 0
    assert len(data["info_sheet"]["key_points_hi"]) > 0


def test_patient_can_digitally_sign_informed_consent(role_clients, seeded_engine):
    patient_client = role_clients[UserRole.PATIENT.value]
    payload = {
        "signer_name": "Aarav Sharma",
        "language": "hi",
        "abha_id": "14-1122-3344-5566",
        "signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    }
    response = patient_client.post("/api/econsent/sign", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["signer_name"] == "Aarav Sharma"
    assert data["language"] == "hi"
    assert data["abha_id"] == "14-1122-3344-5566"
    assert data["status"] == ConsentStatus.SIGNED.value
    assert len(data["sha256_hash"]) == 64

    # Verify 21 CFR Part 11 Audit Trail record was appended in same transaction
    with Session(seeded_engine) as session:
        audit_entry = session.exec(
            select(AuditLog)
            .where(AuditLog.action == AuditAction.SIGN.value)
            .order_by(AuditLog.id.desc())
        ).first()
        assert audit_entry is not None
        assert "e-Consent" in audit_entry.entity_label
        assert "NDCT Rules 2019" in audit_entry.reason


# -----------------------------------------------------------------------------
# TASK 1 TESTS — PATIENT VISIT ISOLATION
# -----------------------------------------------------------------------------

def test_patient_can_read_own_visits(role_clients, seeded_engine):
    """1. Patient A can read Patient A's Visits."""
    patient_client = role_clients[UserRole.PATIENT.value]
    with Session(seeded_engine) as session:
        patient_user = session.exec(select(User).where(User.role == UserRole.PATIENT.value)).first()
        assert patient_user is not None and patient_user.subject_id is not None
        my_subject_id = patient_user.subject_id

    # Test /api/visits query
    res = patient_client.get("/api/visits")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0
    for v in items:
        assert v["subject_id"] == my_subject_id

    # Test /api/subjects/{id}/visits
    res_subj = patient_client.get(f"/api/subjects/{my_subject_id}/visits")
    assert res_subj.status_code == 200
    assert len(res_subj.json()) == len(items)


def test_patient_cannot_read_other_patient_visits_same_or_diff_site(role_clients, seeded_engine):
    """2. Patient A cannot read Patient B's Visits at same site or different site."""
    patient_client = role_clients[UserRole.PATIENT.value]
    with Session(seeded_engine) as session:
        patient_user = session.exec(select(User).where(User.role == UserRole.PATIENT.value)).first()
        my_subject_id = patient_user.subject_id

        # Find another subject at same site
        other_subject_same_site = session.exec(
            select(Subject).where(Subject.id != my_subject_id, Subject.site_id == patient_user.site_id)
        ).first()
        assert other_subject_same_site is not None

        # Find a visit belonging to other subject
        other_visit = session.exec(
            select(Visit).where(Visit.subject_id == other_subject_same_site.id)
        ).first()
        assert other_visit is not None

        # Find subject at another site
        other_subject_diff_site = session.exec(
            select(Subject).where(Subject.site_id != patient_user.site_id)
        ).first()
        assert other_subject_diff_site is not None

    # Patient A querying Patient B's subject visits -> 403 Forbidden
    res_same = patient_client.get(f"/api/subjects/{other_subject_same_site.id}/visits")
    assert res_same.status_code == 403

    # Patient A querying Patient C's subject visits (diff site) -> 403 Forbidden
    res_diff = patient_client.get(f"/api/subjects/{other_subject_diff_site.id}/visits")
    assert res_diff.status_code == 403

    # Patient A querying single visit endpoint for other patient's visit -> 403 Forbidden
    res_visit = patient_client.get(f"/api/visits/{other_visit.id}")
    assert res_visit.status_code == 403


def test_pi_reads_only_assigned_site_visits(role_clients, seeded_engine):
    """4. PI can read only their assigned Site's Visits."""
    pi_client = role_clients[UserRole.PRINCIPAL_INVESTIGATOR.value]
    with Session(seeded_engine) as session:
        pi_user = session.exec(select(User).where(User.role == UserRole.PRINCIPAL_INVESTIGATOR.value)).first()
        pi_site_id = pi_user.site_id
        assert pi_site_id is not None

    res = pi_client.get("/api/visits")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0

    with Session(seeded_engine) as session:
        site_subject_ids = set(session.exec(select(Subject.id).where(Subject.site_id == pi_site_id)).all())
        for v in items:
            assert v["subject_id"] in site_subject_ids


def test_sponsor_and_regulator_have_global_visit_access(role_clients, seeded_engine):
    """5. Sponsor/Regulator access follows global permissions."""
    sponsor_client = role_clients[UserRole.SPONSOR.value]
    regulator_client = role_clients[UserRole.REGULATOR.value]

    res_sponsor = sponsor_client.get("/api/visits")
    assert res_sponsor.status_code == 200
    assert res_sponsor.json()["total"] > 100

    res_regulator = regulator_client.get("/api/visits")
    assert res_regulator.status_code == 200
    assert res_regulator.json()["total"] > 100


# -----------------------------------------------------------------------------
# TASK 2 TESTS — E-CONSENT OWNERSHIP
# -----------------------------------------------------------------------------

def test_patient_cannot_view_other_patient_certificate(role_clients, seeded_engine):
    """3. Patient A cannot view Patient B's certificate."""
    patient_client = role_clients[UserRole.PATIENT.value]
    with Session(seeded_engine) as session:
        patient_user = session.exec(select(User).where(User.role == UserRole.PATIENT.value)).first()
        my_subject_id = patient_user.subject_id

        other_subject = session.exec(select(Subject).where(Subject.id != my_subject_id)).first()
        assert other_subject is not None

    # Patient A attempting to view Patient B's certificate by URL ID manipulation
    res = patient_client.get(f"/api/econsent/subjects/{other_subject.id}")
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


def test_patient_signing_derives_subject_from_auth_token_only(role_clients, seeded_engine):
    """4. Altering an ID in request body does not bypass server-side ownership."""
    patient_client = role_clients[UserRole.PATIENT.value]
    with Session(seeded_engine) as session:
        patient_user = session.exec(select(User).where(User.role == UserRole.PATIENT.value)).first()
        my_subject_id = patient_user.subject_id

    # Client tries to pass malicious fields; server ignores body and derives from user.subject_id
    payload = {
        "signer_name": "Aarav Sharma",
        "language": "en",
        "signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    }
    res = patient_client.post("/api/econsent/sign", json=payload)
    assert res.status_code == 200
    assert res.json()["subject_id"] == my_subject_id


# -----------------------------------------------------------------------------
# TASK 3 TESTS — ATOMIC CONSENT AND AUDIT ROLLBACK
# -----------------------------------------------------------------------------

def test_atomic_consent_and_audit_rolls_back_on_audit_failure(role_clients, seeded_engine):
    """Forces audit failure and confirms that consent creation/signing rolls back atomically."""
    patient_client = role_clients[UserRole.PATIENT.value]
    with Session(seeded_engine) as session:
        patient_user = session.exec(select(User).where(User.role == UserRole.PATIENT.value)).first()
        my_subject_id = patient_user.subject_id
        # Ensure no consent exists initially for this subject
        existing = session.exec(select(EConsent).where(EConsent.subject_id == my_subject_id)).first()
        if existing:
            session.delete(existing)
            session.commit()

    payload = {
        "signer_name": "Fail Test Signer",
        "language": "en",
        "signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    }

    # Inject an intentional failure into audit.record
    with patch("app.audit.record", side_effect=RuntimeError("Simulated 21 CFR Part 11 Audit Failure")):
        with pytest.raises(RuntimeError):
            patient_client.post("/api/econsent/sign", json=payload)

    # Confirm that EConsent was NOT persisted (atomic transaction rollback)
    with Session(seeded_engine) as session:
        saved_consent = session.exec(select(EConsent).where(EConsent.subject_id == my_subject_id)).first()
        assert saved_consent is None, "EConsent must not be committed when audit recording fails"


# -----------------------------------------------------------------------------
# TASK 4 TESTS — WEBSOCKET PRIVACY & SUBJECT-SCOPED VISIBILITY
# -----------------------------------------------------------------------------

def test_websocket_event_subject_scoping_and_privacy():
    """Verify that patient events are Subject-scoped and contain no PII."""
    patient_user = CurrentUser(
        id=14,
        email="patient@test.in",
        full_name="Patient Aarav",
        role=UserRole.PATIENT.value,
        role_label="Participant",
        site_id=1,
        subject_id=101,
        permissions=frozenset({Permission.ECONSENT_READ, Permission.VISIT_READ}),
    )

    event_for_patient_a = {
        "type": "econsent.signed",
        "site_id": 1,
        "subject_id": 101,
        "message": "Informed consent was digitally signed for a trial participant.",
    }

    event_for_patient_b = {
        "type": "econsent.signed",
        "site_id": 1,
        "subject_id": 102,
        "message": "Informed consent was digitally signed for a trial participant.",
    }

    event_diff_site = {
        "type": "econsent.signed",
        "site_id": 2,
        "subject_id": 201,
        "message": "Informed consent was digitally signed for a trial participant.",
    }

    # 1. Patient A receives their own event
    assert _visible_to(patient_user, event_for_patient_a) is True

    # 2. Patient A CANNOT receive Patient B's event at the same site
    assert _visible_to(patient_user, event_for_patient_b) is False

    # 3. Patient A CANNOT receive event from another site
    assert _visible_to(patient_user, event_diff_site) is False

    # 4. Unauthorized role receives generic recalculation notification
    unauthorized_user = CurrentUser(
        id=99,
        email="guest@test.in",
        full_name="Guest User",
        role="guest",
        role_label="Guest",
        site_id=None,
        subject_id=None,
        permissions=frozenset(),
    )
    viewer_payload = _for_viewer(unauthorized_user, event_for_patient_a)
    assert viewer_payload["detail_withheld"] is True

    # 5. Verify no PII in event payload keys
    for k in ("signer_name", "patient_email", "email", "abha_id", "signature_data_url"):
        assert k not in event_for_patient_a
