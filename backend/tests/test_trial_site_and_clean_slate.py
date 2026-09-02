"""Tests for Trial & Site Provisioning and Production Clean Slate Engine."""

from sqlmodel import Session, select

from app.enums import UserRole
from app.models import Subject, Trial, Site, Visit, AdverseEvent
from tests.conftest import client_for


def test_admin_creates_trial_and_sites(seeded_engine):
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)

    # 1. Create a new clinical trial
    trial_payload = {
        "protocol_number": "AIIA-NEO-2026-02",
        "title": "A Multi-Centric Efficacy Trial of Ayush-64 in Metabolic Syndrome",
        "short_title": "Ayush-64 Metabolic Trial",
        "phase": "phase_3",
        "indication": "Metabolic Syndrome (Medoroga)",
        "indication_ayurveda": "Sthoulya & Medoroga",
        "intervention": "Ayush-64 Tablets 500mg TID",
        "comparator": "Standard Care Control",
        "design": "Randomized, Double-Blind, Active-Controlled Trial",
        "sponsor_name": "Ministry of Ayush / AIIA",
        "target_enrollment": 150,
    }
    res = admin_client.post("/api/trials", json=trial_payload)
    assert res.status_code == 201, res.text
    trial_data = res.json()
    assert trial_data["protocol_number"] == "AIIA-NEO-2026-02"
    assert trial_data["status"] == "planning"
    new_trial_id = trial_data["id"]

    # 2. Add participating hospital sites to the trial
    site_payload = {
        "trial_id": new_trial_id,
        "site_code": "03",
        "name": "Institute of Post Graduate Teaching & Research in Ayurveda",
        "city": "Jamnagar",
        "state": "Gujarat",
        "country": "India",
        "pi_name": "Dr. Anup Thakar",
        "pi_email": "pi.jamnagar@aiia-ctms.in",
        "contact_phone": "+91 288 2552555",
        "status": "activated",
        "target_enrollment": 50,
    }
    site_res = admin_client.post("/api/sites", json=site_payload)
    assert site_res.status_code == 201, site_res.text
    site_data = site_res.json()
    assert site_data["site_code"] == "03"
    assert site_data["city"] == "Jamnagar"
    assert site_data["trial_id"] == new_trial_id


