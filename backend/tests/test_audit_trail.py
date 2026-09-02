"""Tests for ALCOA+ Immutable Audit Trail & Filtering under 21 CFR Part 11."""

from sqlmodel import Session, select

from app.enums import UserRole
from app.models import AuditLog, Trial
from tests.conftest import client_for


def test_audit_trail_immutable_and_searchable(seeded_engine):
    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)

    # 1. Fetch audit log without filters
    res = regulator_client.get("/api/audit-log")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) > 0

    # 2. Filter by entity_type
    res_entity = regulator_client.get("/api/audit-log?entity_type=trials")
    assert res_entity.status_code == 200
    entity_data = res_entity.json()
    for item in entity_data["items"]:
        assert item["entity_type"] == "trials"

    # 3. Filter by action
    res_action = regulator_client.get("/api/audit-log?action=update")
    assert res_action.status_code == 200
    action_data = res_action.json()
    for item in action_data["items"]:
        assert item["action"] == "update"

    # 4. Search term in reason or label
    res_search = regulator_client.get("/api/audit-log?search=ash")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert isinstance(search_data["items"], list)

    # 5. Non-oversight role (e.g. Coordinator / Investigator) is forbidden (403)
    coord_client = client_for(seeded_engine, UserRole.COORDINATOR.value)
    coord_res = coord_client.get("/api/audit-log")
    assert coord_res.status_code == 403
    assert "Missing permission: audit:read" in coord_res.json()["detail"]
