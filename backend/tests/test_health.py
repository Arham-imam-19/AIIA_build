"""Phase 0 smoke tests.

Run with:  docker compose exec backend pytest

These are the only tests that talk to the *real* DATABASE_URL rather than a
throwaway SQLite file, which is the point: they check that the container can
reach its database. On a laptop with no Postgres running,
`test_health_database_is_connected` is expected to fail - run the suite inside
Docker, or deselect it.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """A client with no dependency overrides in place.

    conftest.py's clients redirect `get_session` at a test database. This module
    wants the genuine one, so any leftover override is removed first.
    """
    app.dependency_overrides.clear()
    return TestClient(app)


def test_root_returns_app_metadata(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "AIIA Clinical Trials Dashboard"


def test_health_reports_database_status(client):
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body
    assert isinstance(body["database"]["ok"], bool)


def test_health_database_is_connected(client):
    """Inside Docker Compose the database must actually be reachable."""
    body = client.get("/api/health").json()
    assert body["database"]["ok"] is True, body["database"]["detail"]
    assert body["status"] == "ok"


def test_info_lists_the_five_features_and_five_roles(client):
    body = client.get("/api/info").json()
    assert len(body["features"]) == 5
    assert len(body["roles"]) == 5
    assert "synthetic" in body["data_notice"].lower()
