"""Tests for IT Admin global test data reset and control plane."""

from app.enums import UserRole
from tests.conftest import client_for


def test_admin_database_stats(seeded_engine):
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)
    res = admin_client.get("/api/admin/database-stats")
    assert res.status_code == 200
    data = res.json()
    assert data["trials"] > 0
    assert data["sites"] > 0
    assert data["subjects"] > 0
    assert data["visits"] > 0


def test_unauthorized_user_cannot_reset_test_data(seeded_engine):
    coord_client = client_for(seeded_engine, UserRole.COORDINATOR.value)
    res = coord_client.post("/api/admin/reset-trial-data")
    assert res.status_code == 403


def test_admin_clean_slate_reset_wipes_all_test_data(seeded_engine):
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)

    # Execute clean slate reset
    res = admin_client.post("/api/admin/reset-trial-data")
    assert res.status_code == 200
    result = res.json()
    assert result["status"] == "success"
    assert result["cleared_subjects"] > 0
    assert result["cleared_visits"] > 0
    assert result["cleared_adverse_events"] >= 0
    assert result["preserved_sites"] > 0
    assert result["preserved_staff_users"] > 0

    # Verify all transactional data is gone
    stats_res = admin_client.get("/api/admin/database-stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["subjects"] == 0
    assert stats["visits"] == 0
    assert stats["adverse_events"] == 0
    assert stats["clinical_logs"] == 0
    assert stats["econsents"] == 0
    assert stats["trials"] > 0
    assert stats["sites"] > 0
    assert stats["users"] > 0
