"""Tests for role-based access control and site scoping.

Phase 2 added JWT authentication and RBAC. These tests verify:
  * unauthenticated requests are refused cleanly
  * every role receives exactly the permissions `ROLE_PERMISSIONS` promises
  * site scoping works: a site user cannot see another site's rows
  * the live /api/rbac-matrix matches the actual enforcement
"""

from __future__ import annotations

import pytest

from app.enums import UserRole
from app.models import Site, Subject
from app.rbac import (
    PERMISSION_LABELS,
    ROLE_LABELS,
    Permission,
    SITE_SCOPED_ROLES,
)

# Every listing endpoint, and the permission its own decorator demands. Written
# out by hand rather than introspected, so that removing a `require(...)` from a
# router shows up here as a failure instead of quietly agreeing with itself.
GUARDED_LISTS = [
    ("/api/trials", Permission.TRIAL_READ),
    ("/api/sites", Permission.SITE_READ),
    ("/api/subjects", Permission.SUBJECT_READ),
    ("/api/visits", Permission.VISIT_READ),
    ("/api/adverse-events", Permission.AE_READ),
    ("/api/patient-requests", Permission.PATIENT_REQUEST_READ),
    ("/api/econsent/my", Permission.ECONSENT_READ),
    ("/api/audit-log", Permission.AUDIT_READ),
    ("/api/users", Permission.USER_READ),
    ("/api/stats", Permission.TRIAL_READ),
    ("/api/dashboard", Permission.TRIAL_READ),
]

ROLES = [
    UserRole.ADMIN.value,
    UserRole.INSTITUTION_ADMIN.value,
    UserRole.PRINCIPAL_INVESTIGATOR.value,
    UserRole.COORDINATOR.value,
    UserRole.PATIENT.value,
    UserRole.SPONSOR.value,
    UserRole.ETHICS_COMMITTEE.value,
    UserRole.REGULATOR.value,
]


@pytest.fixture(scope="module")
def any_subject_id(seeded_engine) -> int:
    from sqlmodel import Session, select

    with Session(seeded_engine) as session:
        return session.exec(select(Subject.id)).first()  # type: ignore[return-value]


@pytest.fixture(scope="module")
def site_two_subject_id(seeded_engine) -> int:
    """A subject at site 02, so a site 01 user is refused."""
    from sqlmodel import Session, select

    with Session(seeded_engine) as session:
        site_two = session.exec(select(Site).where(Site.site_code == "02")).first()
        assert site_two is not None
        subject = session.exec(
            select(Subject).where(Subject.site_id == site_two.id)
        ).first()
        assert subject is not None
        return subject.id  # type: ignore[return-value]


# -------------------------------------------------------- unauthenticated calls


@pytest.mark.parametrize("path, _permission", GUARDED_LISTS)
def test_unauthenticated_requests_are_refused_on_every_guarded_endpoint(
    anonymous_client, path, _permission
):
    response = anonymous_client.get(path)
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    # Make sure we got our own helpful detail, not FastAPI's bare default.
    assert "not signed in" in response.json()["detail"]


def test_a_bad_token_is_refused(client):
    response = client.get(
        "/api/trials", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401


# ------------------------------------------------------------- role permissions


def test_the_admin_can_access_every_endpoint(role_clients):
    admin = role_clients[UserRole.ADMIN.value]
    for path, _permission in GUARDED_LISTS:
        assert admin.get(path).status_code == 200, path


def test_the_investigator_cannot_read_the_audit_log(role_clients):
    """The investigator sees clinical data, not the compliance audit trail."""
    pi = role_clients[UserRole.PRINCIPAL_INVESTIGATOR.value]
    response = pi.get("/api/audit-log")
    assert response.status_code == 403
    assert "Missing permission: audit:read" in response.json()["detail"]


def test_the_coordinator_cannot_read_compliance_or_audit(role_clients):
    crc = role_clients[UserRole.COORDINATOR.value]
    assert crc.get("/api/audit-log").status_code == 403
    # CRC has write permissions on visits, so simulation succeeds.
    assert crc.get("/api/simulate/options").status_code == 200


def test_the_ethics_committee_cannot_browse_participants(role_clients):
    """The committee reviews safety and deviations, not individual people.

    A key part of the pitch: ethics oversight is about protocols and safety
    signals, so participants are not exposed unnecessarily.
    """
    ethics = role_clients[UserRole.ETHICS_COMMITTEE.value]
    assert ethics.get("/api/adverse-events").status_code == 200
    assert ethics.get("/api/visits").status_code == 200
    assert ethics.get("/api/audit-log").status_code == 200
    assert ethics.get("/api/subjects").status_code == 403


def test_the_sponsor_can_read_everything_and_change_nothing(role_clients):
    """A monitor who could edit the data would undermine the data."""
    sponsor = role_clients[UserRole.SPONSOR.value]
    for path, permission in GUARDED_LISTS:
        if permission in (Permission.AUDIT_READ, Permission.PATIENT_REQUEST_READ):
            continue  # the audit trail is for ethics/regulator, and patient requests are for institution admins/patients
        assert sponsor.get(path).status_code == 200, path

    for action in ("enrollment", "adverse-event", "deviation"):
        response = sponsor.post(f"/api/simulate/{action}", json={})
        assert response.status_code == 403, action


def test_the_regulator_is_read_only_across_every_site(role_clients):
    regulator = role_clients[UserRole.REGULATOR.value]
    assert regulator.get("/api/audit-log").status_code == 200
    assert regulator.get("/api/subjects").status_code == 200
    for action in ("enrollment", "adverse-event", "deviation"):
        response = regulator.post(f"/api/simulate/{action}", json={})
        assert response.status_code == 403, action


# ----------------------------------------------------------------- site scoping


def test_the_investigator_sees_only_their_own_site_in_listings(role_clients):
    pi = role_clients[UserRole.PRINCIPAL_INVESTIGATOR.value]
    # Listing sites returns exactly one site (the PI's own).
    sites = pi.get("/api/sites").json()["items"]
    assert len(sites) == 1
    assert sites[0]["site_code"] == "01"

    # Listing participants returns only participants from site 01.
    subjects = pi.get("/api/subjects").json()["items"]
    assert len(subjects) > 0
    assert all(s["subject_code"].startswith("AIIA-ASH-01-") for s in subjects)


def test_the_coordinator_sees_only_their_own_site_in_listings(role_clients):
    crc = role_clients[UserRole.COORDINATOR.value]
    sites = crc.get("/api/sites").json()["items"]
    assert len(sites) == 1
    assert sites[0]["site_code"] == "01"


def test_asking_for_another_sites_subject_by_id_returns_403(
    role_clients, site_two_subject_id
):
    """The hard-scoping invariant: asking for another site's row by id refuses
    loudly (403), rather than hiding it with a 404."""
    pi = role_clients[UserRole.PRINCIPAL_INVESTIGATOR.value]
    response = pi.get(f"/api/subjects/{site_two_subject_id}")
    assert response.status_code == 403
    assert "belongs to another site" in response.json()["detail"]


def test_an_oversight_role_can_fetch_a_subject_from_any_site(
    role_clients, site_two_subject_id
):
    sponsor = role_clients[UserRole.SPONSOR.value]
    response = sponsor.get(f"/api/subjects/{site_two_subject_id}")
    assert response.status_code == 200
    assert response.json()["id"] == site_two_subject_id


# ------------------------------------------------------------- simulate options


def test_simulate_options_explains_allowed_actions_per_role(role_clients):
    pi = role_clients[UserRole.PRINCIPAL_INVESTIGATOR.value]
    options = pi.get("/api/simulate/options").json()["actions"]
    # PI has AE_WRITE and SUBJECT_WRITE, so both are allowed.
    assert any(a["key"] == "enrollment" and a["allowed"] for a in options)
    assert any(a["key"] == "adverse-event" and a["allowed"] for a in options)

    sponsor = role_clients[UserRole.SPONSOR.value]
    sponsor_options = sponsor.get("/api/simulate/options").json()["actions"]
    # Sponsor is read-only, so none are allowed, but each carries a reason.
    assert all(not a["allowed"] for a in sponsor_options)
    assert all(a["reason"] for a in sponsor_options)


# ------------------------------------------------------- authentication session


def test_login_returns_token_and_populated_user_payload(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "meenakshi.sharma@demo.aiia-ctms.in",
            "password": "aiia2026",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "meenakshi.sharma@demo.aiia-ctms.in"
    assert body["user"]["role"] == UserRole.PRINCIPAL_INVESTIGATOR.value
    assert body["user"]["site_scoped"] is True
    assert "ae:write" in body["user"]["permissions"]


def test_login_refuses_wrong_password(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "meenakshi.sharma@demo.aiia-ctms.in",
            "password": "wrong-password",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "incorrect email or password"


def test_me_returns_identity_for_valid_token(client):
    login = client.post(
        "/api/auth/login",
        json={
            "email": "meenakshi.sharma@demo.aiia-ctms.in",
            "password": "aiia2026",
        },
    ).json()
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "meenakshi.sharma@demo.aiia-ctms.in"


def test_me_refuses_expired_or_garbage_token(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-token"},
    )
    assert response.status_code == 401


# ------------------------------------------------------------------ RBAC matrix


def test_the_matrix_lists_every_role_and_permission(client):
    body = client.get("/api/rbac-matrix").json()
    assert {p["key"] for p in body["permissions"]} == {p.value for p in Permission}
    assert {r["key"] for r in body["roles"]} == set(ROLES)
    for role in body["roles"]:
        assert role["label"], role["key"]
        assert role["scope"] in {"own site only", "all sites"}
        assert set(role["granted"]) <= {p.value for p in Permission}


def test_the_matrix_marks_exactly_the_site_scoped_roles(client):
    body = client.get("/api/rbac-matrix").json()
    scoped = {role["key"] for role in body["roles"] if role["site_scoped"]}
    assert scoped == {
        UserRole.INSTITUTION_ADMIN.value,
        UserRole.PRINCIPAL_INVESTIGATOR.value,
        UserRole.COORDINATOR.value,
        UserRole.PATIENT.value,
    }


def test_the_published_matrix_is_the_one_being_enforced(client, role_clients):
    """Drive real requests from the table the UI renders.

    If somebody adds a permission to a role in `rbac.py` but the endpoint still
    refuses it - or the other way round - this fails. It is what stops the demo
    screen from claiming something the API does not do.
    """
    published = {
        role["key"]: set(role["granted"])
        for role in client.get("/api/rbac-matrix").json()["roles"]
    }
    for role, granted in published.items():
        for path, permission in GUARDED_LISTS:
            expected = 200 if permission.value in granted else 403
            actual = role_clients[role].get(path).status_code
            assert actual == expected, (
                f"the matrix says {role} "
                f"{'has' if permission.value in granted else 'lacks'} "
                f"{permission.value}, but GET {path} returned {actual}"
            )
