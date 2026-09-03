"""Tests for Sponsor Oversight endpoints: analytics, milestones, SAE queue, and institute drill-down."""

from app.enums import UserRole
from tests.conftest import client_for


def test_sponsor_analytics(seeded_engine):
    client = client_for(seeded_engine, UserRole.SPONSOR.value)
    res = client.get("/api/sponsor/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "enrollment_curve" in data
    assert "safety_distribution" in data
    assert "deltas" in data
    assert "consent_compliance_pct" in data


def test_sponsor_regulatory_milestones(seeded_engine):
    client = client_for(seeded_engine, UserRole.SPONSOR.value)
    res = client.get("/api/sponsor/regulatory-milestones")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        trial = data[0]
        assert "ctri_status" in trial
        assert "ec_status" in trial
        assert "renewal_status" in trial


def test_sponsor_sae_queue(seeded_engine):
    client = client_for(seeded_engine, UserRole.SPONSOR.value)
    res = client.get("/api/sponsor/sae-queue")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    for sae in data:
        assert "clock_status" in sae
        assert "clock_label" in sae
        assert "hours_remaining" in sae


def test_sponsor_institute_drilldown(seeded_engine):
    client = client_for(seeded_engine, UserRole.SPONSOR.value)
    # Fetch trial sites first
    sites_res = client.get("/api/sites")
    assert sites_res.status_code == 200
    sites = sites_res.json().get("items", [])
    if sites:
        target_site_id = sites[0]["id"]
        res = client.get(f"/api/sponsor/institutes/{target_site_id}/drilldown")
        assert res.status_code == 200
        drilldown = res.json()
        assert drilldown["site_id"] == target_site_id
        assert "studies" in drilldown
        assert len(drilldown["studies"]) > 0


def test_site_scoped_role_is_denied_portfolio_sponsor_api(seeded_engine):
    coordinator_client = client_for(seeded_engine, UserRole.COORDINATOR.value)
    res = coordinator_client.get("/api/sponsor/analytics")
    assert res.status_code == 403

    pi_client = client_for(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    res_pi = pi_client.get("/api/sponsor/regulatory-milestones")
    assert res_pi.status_code == 403


def test_unauthenticated_request_is_denied(client):
    res = client.get("/api/sponsor/analytics")
    assert res.status_code in {401, 403}
