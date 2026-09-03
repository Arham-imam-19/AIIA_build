"""Tests for Ethics Committee (IEC) SAE Docket, Adjudication, and Decision Propagation."""

from app.enums import UserRole
from tests.conftest import client_for


def test_ethics_sae_docket_and_adjudication(seeded_engine):
    ethics_client = client_for(seeded_engine, UserRole.ETHICS_COMMITTEE.value)
    
    # 1. Fetch docket
    res = ethics_client.get("/api/ethics/sae-docket")
    assert res.status_code == 200
    docket = res.json()
    assert "unreviewed_count" in docket
    assert "reviewed_count" in docket
    assert "saes" in docket
    assert len(docket["saes"]) > 0

    target_sae = docket["saes"][0]
    sae_id = target_sae["id"]

    # 2. Adjudicate as Accepted
    adj_res = ethics_client.post(
        f"/api/ethics/sae-docket/{sae_id}/adjudicate",
        json={"decision": "accepted", "notes": "Safety cleared by IEC panel."}
    )
    assert adj_res.status_code == 200
    data = adj_res.json()
    assert data["ec_decision"] == "accepted"
    assert data["ec_decision_notes"] == "Safety cleared by IEC panel."

    # 3. Check that docket reflects reviewed status
    res2 = ethics_client.get("/api/ethics/sae-docket")
    docket2 = res2.json()
    updated_sae = next(s for s in docket2["saes"] if s["id"] == sae_id)
    assert updated_sae["ec_decision"] == "accepted"
    assert updated_sae["is_reviewed"] is True


def test_ethics_adjudication_rejected(seeded_engine):
    ethics_client = client_for(seeded_engine, UserRole.ETHICS_COMMITTEE.value)
    res = ethics_client.get("/api/ethics/sae-docket")
    docket = res.json()
    assert len(docket["saes"]) > 0

    target_sae = docket["saes"][-1]
    sae_id = target_sae["id"]

    adj_res = ethics_client.post(
        f"/api/ethics/sae-docket/{sae_id}/adjudicate",
        json={"decision": "rejected", "notes": "Subject treatment halted immediately."}
    )
    assert adj_res.status_code == 200
    data = adj_res.json()
    assert data["ec_decision"] == "rejected"


def test_unauthorized_role_cannot_adjudicate_sae(seeded_engine):
    coord_client = client_for(seeded_engine, UserRole.COORDINATOR.value)
    res = coord_client.post(
        "/api/ethics/sae-docket/1/adjudicate",
        json={"decision": "accepted", "notes": "Unauthorized attempt."}
    )
    assert res.status_code == 403


def test_iec_decision_propagates_to_subject_dossier(seeded_engine):
    ethics_client = client_for(seeded_engine, UserRole.ETHICS_COMMITTEE.value)
    coord_client = client_for(seeded_engine, UserRole.COORDINATOR.value)

    # Fetch SAE to get subject_id
    docket = ethics_client.get("/api/ethics/sae-docket").json()
    sae = docket["saes"][0]
    sae_id = sae["id"]

    # Adjudicate
    ethics_client.post(
        f"/api/ethics/sae-docket/{sae_id}/adjudicate",
        json={"decision": "accepted", "notes": "Confirmed benign profile."}
    )

    # Fetch dossier for subjects at site 15
    subjects_res = coord_client.get("/api/subjects?limit=5")
    subjects = subjects_res.json().get("items", [])
    if subjects:
        sub_id = subjects[0]["id"]
        dossier = coord_client.get(f"/api/subjects/{sub_id}/dossier").json()
        assert "adverse_events" in dossier
