"""Tests for Role-Aware Response Blinding of Subjects and Clinical Allocation.

Ensures that roles requiring blinding (e.g. Sponsor) receive subject demographic
and recruitment data without leaking unblinded treatment allocation fields ('arm', 'randomization_date').
"""

import pytest
from app.enums import UserRole
from tests.conftest import client_for


def test_sponsor_list_subjects_is_blinded(seeded_engine):
    """Sponsor querying /api/subjects must NOT receive 'arm' or 'randomization_date'."""
    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)

    res = sponsor_client.get("/api/subjects")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) > 0

    for subject in data["items"]:
        # Assert neither 'arm' nor 'randomization_date' is present in serialized output
        assert "arm" not in subject, f"Blinding leak: 'arm' present in {subject}"
        assert "randomization_date" not in subject, f"Blinding leak: 'randomization_date' present in {subject}"
        # Assert required demographic/funnel fields ARE present
        assert "id" in subject
        assert "subject_code" in subject
        assert "status" in subject
        assert "screening_date" in subject
        assert "sex" in subject


def test_sponsor_get_single_subject_is_blinded(seeded_engine):
    """Sponsor querying /api/subjects/{id} must NOT receive 'arm' or 'randomization_date'."""
    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)

    # First get a subject ID
    list_res = sponsor_client.get("/api/subjects?limit=1")
    assert list_res.status_code == 200
    sub_id = list_res.json()["items"][0]["id"]

    res = sponsor_client.get(f"/api/subjects/{sub_id}")
    assert res.status_code == 200
    subject = res.json()

    assert "arm" not in subject, f"Blinding leak: 'arm' present in single subject {subject}"
    assert "randomization_date" not in subject, f"Blinding leak: 'randomization_date' present in single subject {subject}"
    assert subject["id"] == sub_id


def test_sponsor_subject_dossier_is_blinded(seeded_engine):
    """Sponsor querying /api/subjects/{id}/dossier must have arm masked as [BLINDED]."""
    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)

    list_res = sponsor_client.get("/api/subjects?limit=1")
    sub_id = list_res.json()["items"][0]["id"]

    res = sponsor_client.get(f"/api/subjects/{sub_id}/dossier")
    assert res.status_code == 200
    dossier = res.json()

    profile = dossier["profile"]
    assert profile["arm"] == "[BLINDED]"
    assert profile["randomization_date"] is None
    assert profile["is_blinded"] is True

    # Check timeline events do not leak arm
    for evt in dossier["timeline"]:
        if evt["event_type"] == "enrollment":
            assert evt["details"].get("Assigned Study Arm") == "[BLINDED]"
            assert "Randomization Date" not in evt["details"]


def test_unblinded_roles_receive_arm_and_randomization_date(seeded_engine):
    """Non-blinded roles (e.g. Principal Investigator, Admin) must still receive unblinded fields."""
    pi_client = client_for(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)

    res = pi_client.get("/api/subjects")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) > 0

    first_sub = data["items"][0]
    assert "arm" in first_sub
    assert first_sub["arm"] in {"treatment", "placebo", "comparator", "not_randomized"}

    # Single subject check
    single_res = pi_client.get(f"/api/subjects/{first_sub['id']}")
    assert single_res.status_code == 200
    single_sub = single_res.json()
    assert "arm" in single_sub
    assert single_sub["arm"] == first_sub["arm"]
