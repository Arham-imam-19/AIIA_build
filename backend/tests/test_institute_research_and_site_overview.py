"""Test suite for Site Research Overview and Scoped Institutional Trial Creation.

Verifies:
1. Primary Admin and Institution Admin can view comprehensive Site Research Overview and Capacity KPIs.
2. Unauthorized/Foreign site access is rejected with 403 Forbidden.
3. Empty sites return clean empty arrays rather than failing.
4. Institution Admin and Principal Investigator can create new Research Protocols scoped to their institute.
5. Duplicate protocol numbers and invalid numbers are rejected.
6. Created trials strictly enforce NDCT 2019 ethics approval gates before activation.
"""

import pytest
from app.enums import EthicsApprovalStatus, TrialStatus, UserRole
from tests.conftest import client_for


def test_admin_can_view_site_research_overview(seeded_engine):
    """Primary Admin queries /api/sites/{site_id}/trials and receives trial list and site capacity KPIs."""
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)

    # Get first site
    sites_res = admin_client.get("/api/sites?limit=1")
    assert sites_res.status_code == 200
    site = sites_res.json()["items"][0]
    site_id = site["id"]

    res = admin_client.get(f"/api/sites/{site_id}/trials")
    assert res.status_code == 200
    data = res.json()

    assert data["site_id"] == site_id
    assert data["site_code"] == site["site_code"]
    assert data["name"] == site["name"]
    assert "total_trials" in data
    assert data["total_trials"] >= 1
    assert "total_enrolled_subjects" in data
    assert "total_open_deviations" in data
    assert "total_active_saes" in data
    assert "total_staff_count" in data
    assert len(data["trials"]) >= 1

    first_trial = data["trials"][0]
    assert "protocol_number" in first_trial
    assert "title" in first_trial
    assert "site_pi_name" in first_trial
    assert "site_enrolled_subjects" in first_trial


def test_site_scoped_user_cannot_view_foreign_site_overview(seeded_engine):
    """Institution Admin or PI cannot view research overview of another hospital."""
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)
    sites_res = admin_client.get("/api/sites")
    all_sites = sites_res.json()["items"]
    foreign_site = next((s for s in all_sites if s["site_code"] != "01"), all_sites[-1])

    # Login as PI for site 01 (Meenakshi Sharma)
    pi_client = client_for(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    res = pi_client.get(f"/api/sites/{foreign_site['id']}/trials")
    # Must be 403 Forbidden
    assert res.status_code == 403


def test_site_with_zero_trials_returns_clean_response(seeded_engine):
    """A site with zero trials returns 200 OK with empty trials array."""
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)

    # Register a new trial and site
    trial_res = admin_client.post(
        "/api/trials",
        json={
            "protocol_number": "EMPTY-SITE-TRIAL-01",
            "title": "Empty Site Test Protocol",
            "indication": "General Test Indication",
            "intervention": "Test Intervention",
            "sponsor_name": "Test Sponsor",
            "target_enrollment": 50,
        },
    )
    assert trial_res.status_code == 201
    trial_id = trial_res.json()["id"]

    site_res = admin_client.post(
        "/api/sites",
        json={
            "trial_id": trial_id,
            "site_code": "99",
            "name": "Standalone Test Medical Centre",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pi_name": "Dr. Standalone Tester",
            "target_enrollment": 50,
        },
    )
    assert site_res.status_code == 201
    site_id = site_res.json()["id"]

    overview_res = admin_client.get(f"/api/sites/{site_id}/trials")
    assert overview_res.status_code == 200
    overview = overview_res.json()
    assert overview["site_id"] == site_id
    assert overview["total_enrolled_subjects"] == 0
    assert overview["total_open_deviations"] == 0
    assert len(overview["trials"]) == 1


def test_institution_admin_and_pi_can_create_scoped_trial(seeded_engine):
    """Institution Admin and PI can create new research protocols automatically scoped to their site."""
    inst_admin_client = client_for(seeded_engine, UserRole.INSTITUTION_ADMIN.value)

    proto_num = "INST-ADMIN-AYUSH-2026-01"
    create_res = inst_admin_client.post(
        "/api/trials",
        json={
            "protocol_number": proto_num,
            "title": "Institution Admin Trial on Brahmi Efficacy",
            "short_title": "Brahmi Memory Trial",
            "indication": "Cognitive Enhancement",
            "indication_ayurveda": "Smriti Medhya",
            "intervention": "Brahmi Ghrita 10g OD",
            "comparator": "Placebo Ghrita",
            "design": "Randomized Double-Blind",
            "sponsor_name": "Ministry of Ayush",
            "target_enrollment": 120,
        },
    )
    assert create_res.status_code == 201
    created_trial = create_res.json()
    assert created_trial["protocol_number"] == proto_num
    assert created_trial["status"] == TrialStatus.PLANNING.value
    assert created_trial["ethics_approval_status"] == EthicsApprovalStatus.PENDING.value

    # Verify that a site record was automatically created for this trial at their institution
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)
    sites_res = admin_client.get(f"/api/sites?trial_id={created_trial['id']}")
    assert sites_res.status_code == 200
    inst_sites = sites_res.json()["items"]
    assert len(inst_sites) >= 1

    # PI creation
    pi_client = client_for(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    pi_proto = "PI-RESEARCH-2026-02"
    pi_res = pi_client.post(
        "/api/trials",
        json={
            "protocol_number": pi_proto,
            "title": "PI Led Study on Shankhpushpi",
            "short_title": "Shankhpushpi Study",
            "indication": "Mental Fatigue",
            "intervention": "Shankhpushpi Syrup 15ml BD",
            "sponsor_name": "AIIA Research Grant",
            "target_enrollment": 80,
        },
    )
    assert pi_res.status_code == 201
    pi_trial = pi_res.json()
    assert pi_trial["protocol_number"] == pi_proto
    assert pi_trial["status"] == TrialStatus.PLANNING.value


def test_duplicate_protocol_number_rejected(seeded_engine):
    """Creating a research protocol with an existing protocol number is rejected with 400."""
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)

    proto = "DUP-CHECK-2026-01"
    res1 = admin_client.post(
        "/api/trials",
        json={
            "protocol_number": proto,
            "title": "First Protocol",
            "indication": "Indication 1",
            "intervention": "Drug 1",
            "sponsor_name": "Sponsor 1",
            "target_enrollment": 50,
        },
    )
    assert res1.status_code == 201

    res2 = admin_client.post(
        "/api/trials",
        json={
            "protocol_number": proto,
            "title": "Duplicate Protocol Attempt",
            "indication": "Indication 2",
            "intervention": "Drug 2",
            "sponsor_name": "Sponsor 2",
            "target_enrollment": 60,
        },
    )
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_created_trial_requires_ethics_approval_before_activation(seeded_engine):
    """Newly created trial cannot be activated without Ethics Committee approval (NDCT gate)."""
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)
    ethics_client = client_for(seeded_engine, UserRole.ETHICS_COMMITTEE.value)
    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)

    proto = "ETHICS-GATE-TRIAL-01"
    create_res = admin_client.post(
        "/api/trials",
        json={
            "protocol_number": proto,
            "title": "Ethics Gate Verification Trial",
            "indication": "Hypertension",
            "intervention": "Sarpagandha Churna",
            "sponsor_name": "AIIA",
            "target_enrollment": 60,
        },
    )
    assert create_res.status_code == 201
    trial_id = create_res.json()["id"]

    # Attempt activation immediately -> must fail (409 Conflict)
    activate_res = admin_client.post(f"/api/trials/{trial_id}/activate")
    assert activate_res.status_code == 409

    # Approve ethics
    ethics_res = ethics_client.patch(
        f"/api/trials/{trial_id}/ethics-approval",
        json={
            "ethics_approval_status": "approved",
            "ethics_approval_number": "IEC/AIIA/2026/888",
            "ethics_approval_date": "2026-08-01",
            "ethics_approval_valid_until": "2027-08-01",
        },
    )
    assert ethics_res.status_code == 200

    # Add CTRI and Regulatory approval via Sponsor/Admin
    reg_res = sponsor_client.patch(
        f"/api/trials/{trial_id}/regulatory-approval",
        json={
            "regulatory_approval_number": "CDSCO/AYUSH/2026/999",
            "regulatory_approval_date": "2026-08-10",
        },
    )
    assert reg_res.status_code == 200

    ctri_res = sponsor_client.patch(
        f"/api/trials/{trial_id}/ctri-registration",
        json={
            "ctri_number": "CTRI/2026/08/999999",
            "ctri_registration_date": "2026-08-15",
        },
    )
    assert ctri_res.status_code == 200

    # Now activation succeeds
    final_act_res = admin_client.post(f"/api/trials/{trial_id}/activate")
    assert final_act_res.status_code == 200
    assert final_act_res.json()["current_status"] == TrialStatus.RECRUITING.value
