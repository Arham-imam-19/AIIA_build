"""Phase 2: who can see and do what, and whose rows they get.

**RBAC (role-based access control)** attaches permissions to job titles rather
than to individual people. A hotel keycard opens your floor; the manager's opens
every floor.

Two independent limits are tested here, and they are genuinely separate:

1. **Permission** - may this role touch this *kind* of thing at all? An Ethics
   Committee member has no `subject:read`, so `/api/subjects` is a 403 for them
   no matter which site the participants are at.
2. **Site scope** - whose rows do they get? An investigator has `subject:read`,
   but only for their own hospital. Another site's participant is a 403, not an
   empty result, because a filter you can remove by editing the URL is not
   access control.

The most important test in this file is
`test_the_published_matrix_is_the_one_being_enforced`: it drives real requests
from the same table the UI renders, so the screen cannot claim one thing while
the API does another.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app import rbac
from app.enums import UserRole
from app.models import AdverseEvent, Site, Subject, User, Visit
from app.rbac import Permission
from tests.conftest import (
    ScopedClient,
    client_for,
    client_for_user,
    token_for_user,
    users_by_role,
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
    ("/api/audit-log", Permission.AUDIT_READ),
    ("/api/users", Permission.USER_READ),
    ("/api/stats", Permission.TRIAL_READ),
    ("/api/dashboard", Permission.TRIAL_READ),
]

ROLES = [
    UserRole.PRINCIPAL_INVESTIGATOR.value,
    UserRole.COORDINATOR.value,
    UserRole.SPONSOR.value,
    UserRole.ETHICS_COMMITTEE.value,
    UserRole.REGULATOR.value,
    UserRole.ADMIN.value,
]


@pytest.fixture(scope="module")
def sites(seeded_engine) -> list[Site]:
    with Session(seeded_engine) as session:
        return list(session.exec(select(Site).order_by(Site.id)).all())


@pytest.fixture(scope="module")
def investigators(seeded_engine) -> list[User]:
    """One Principal Investigator per hospital - so we have two different scopes."""
    people = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    assert len(people) >= 2, "the seed should staff more than one site"
    return people


@pytest.fixture(scope="module")
def pi_clients(seeded_engine, investigators) -> list[ScopedClient]:
    """A signed-in client for each investigator, in site order."""
    return [client_for_user(seeded_engine, person) for person in investigators]


# --------------------------------------------------------------- the lock itself


@pytest.mark.parametrize("path, _permission", GUARDED_LISTS)
def test_every_endpoint_requires_a_token(anonymous_client, path, _permission):
    """Phase 1 served all of this to anybody. Phase 2 closed it."""
    response = anonymous_client.get(path)
    assert response.status_code == 401, f"{path} answered without a token"


# ------------------------------------------------- permission, role by role


@pytest.mark.parametrize("path, permission", GUARDED_LISTS)
@pytest.mark.parametrize("role", ROLES)
def test_access_follows_the_permission_table(role_clients, role, path, permission):
    """The single check that ties the table in rbac.py to real HTTP responses."""
    granted = permission in rbac.ROLE_PERMISSIONS[role]
    response = role_clients[role].get(path)
    if granted:
        assert response.status_code == 200, f"{role} should reach {path}: {response.text}"
    else:
        assert response.status_code == 403, f"{role} reached {path} without {permission}"
        assert permission.value in response.json()["detail"]


def test_a_403_says_which_permission_is_missing(role_clients):
    """A refusal that does not say why is a support ticket."""
    body = role_clients[UserRole.ETHICS_COMMITTEE.value].get("/api/subjects").json()
    assert body["detail"] == (
        "Ethics Committee cannot do this. Missing permission: subject:read"
    )


def test_only_ethics_committee_and_admin_can_write_trial_ethics_approval():
    expected = {
        UserRole.ETHICS_COMMITTEE.value,
        UserRole.ADMIN.value,
    }
    granted = {
        role
        for role in ROLES
        if Permission.ETHICS_WRITE in rbac.ROLE_PERMISSIONS[role]
    }
    assert granted == expected


def test_only_sponsor_and_admin_can_write_trial_ctri_registration():
    expected = {
        UserRole.SPONSOR.value,
        UserRole.ADMIN.value,
    }
    granted = {
        role
        for role in ROLES
        if Permission.CTRI_WRITE in rbac.ROLE_PERMISSIONS[role]
    }
    assert granted == expected


def test_only_sponsor_and_admin_can_write_trial_regulatory_approval():
    expected = {
        UserRole.SPONSOR.value,
        UserRole.ADMIN.value,
    }
    granted = {
        role
        for role in ROLES
        if Permission.REGULATORY_WRITE in rbac.ROLE_PERMISSIONS[role]
    }
    assert granted == expected
    assert Permission.REGULATORY_WRITE in rbac.ROLE_PERMISSIONS[UserRole.SPONSOR.value]
    assert Permission.REGULATORY_WRITE in rbac.ROLE_PERMISSIONS[UserRole.ADMIN.value]
    for role in (
        UserRole.REGULATOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
    ):
        assert Permission.REGULATORY_WRITE not in rbac.ROLE_PERMISSIONS[role.value]


def test_the_ethics_committee_reviews_safety_without_browsing_participants(role_clients):
    """A deliberate design decision, not an oversight.

    An independent ethics reviewer's remit is safety events, deviations and
    compliance - not reading through who is enrolled. So they get the adverse
    events and the visit schedule, and are refused the participant list.
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
        if permission is Permission.AUDIT_READ:
            continue  # the audit trail is for ethics and the regulator
        assert sponsor.get(path).status_code == 200, path

    for action in ("enrollment", "adverse-event", "deviation"):
        response = sponsor.post(f"/api/simulate/{action}", json={})
        assert response.status_code == 403, action


def test_the_regulator_is_read_only_across_every_site(role_clients):
    regulator = role_clients[UserRole.REGULATOR.value]
    assert regulator.get("/api/audit-log").status_code == 200
    assert regulator.get("/api/subjects").status_code == 200
    for action in ("enrollment", "adverse-event", "deviation"):
        assert regulator.post(f"/api/simulate/{action}", json={}).status_code == 403


def test_only_the_clinical_site_roles_can_write(role_clients):
    writers = {UserRole.PRINCIPAL_INVESTIGATOR.value, UserRole.COORDINATOR.value,
               UserRole.ADMIN.value}
    for role, client in role_clients.items():
        options = client.get("/api/simulate/options").json()
        allowed = {action["key"] for action in options["actions"] if action["allowed"]}
        if role in writers:
            assert allowed == {"enrollment", "adverse-event", "deviation"}, role
        else:
            assert allowed == set(), role
            # And a greyed-out button has to explain itself.
            for action in options["actions"]:
                assert action["why_not"], f"{role}/{action['key']} has no explanation"


# -------------------------------------------------------------- site scoping


def test_a_site_scoped_user_only_sees_their_own_participants(pi_clients, investigators):
    for client, person in zip(pi_clients, investigators):
        body = client.get("/api/subjects", params={"limit": 500}).json()
        assert body["total"] > 0
        sites = {item["site_id"] for item in body["items"]}
        assert sites == {person.site_id}, f"{person.email} saw sites {sites}"


def test_the_two_investigators_see_different_and_smaller_worlds(
    pi_clients, role_clients, investigators
):
    """Two people in the same job at different hospitals, plus the whole picture."""
    everything = role_clients[UserRole.SPONSOR.value].get(
        "/api/subjects", params={"limit": 500}
    ).json()["total"]
    per_pi = [client.get("/api/subjects").json()["total"] for client in pi_clients]

    assert all(0 < count < everything for count in per_pi)
    # Their views are disjoint slices of the same table, so they cannot add up to
    # more than exists.
    assert sum(per_pi) <= everything


def test_asking_for_another_sites_participant_is_a_403_not_an_empty_page(
    pi_clients, investigators, seeded_engine
):
    """A 404 would invite someone to keep guessing ids. A 403 states the rule."""
    other = investigators[1]
    with Session(seeded_engine) as session:
        theirs = session.exec(
            select(Subject).where(Subject.site_id == other.site_id).order_by(Subject.id)
        ).first()
    assert theirs is not None

    response = pi_clients[0].get(f"/api/subjects/{theirs.id}")
    assert response.status_code == 403
    assert "another site" in response.json()["detail"]
    # But their own site's colleague can open it.
    assert pi_clients[1].get(f"/api/subjects/{theirs.id}").status_code == 200


def test_the_site_filter_cannot_be_used_to_look_at_another_site(pi_clients, investigators):
    """Editing the query string must not widen the scope.

    This is what "hard scoping" means: the filter is applied on top of a query
    that has already been narrowed server-side, so asking for someone else's site
    returns nothing rather than their rows.
    """
    mine, theirs = investigators[0].site_id, investigators[1].site_id
    body = pi_clients[0].get("/api/subjects", params={"site_id": theirs}).json()
    assert body["total"] == 0
    assert body["items"] == []
    # Sanity: the same request for their own site does return rows.
    assert pi_clients[0].get("/api/subjects", params={"site_id": mine}).json()["total"] > 0


def test_scoping_covers_visits_and_adverse_events_too(
    pi_clients, investigators, seeded_engine
):
    """Not just the participant table - every route that reaches a person."""
    other = investigators[1]
    with Session(seeded_engine) as session:
        event = session.exec(
            select(AdverseEvent)
            .where(AdverseEvent.site_id == other.site_id)
            .order_by(AdverseEvent.id)
        ).first()
        subject_ids = session.exec(
            select(Subject.id).where(Subject.site_id == other.site_id)
        ).all()
        visit = session.exec(
            select(Visit).where(Visit.subject_id.in_(subject_ids)).order_by(Visit.id)
        ).first()

    assert pi_clients[0].get(f"/api/adverse-events/{event.id}").status_code == 403
    assert pi_clients[0].get(f"/api/visits/{visit.id}").status_code == 403

    listed = pi_clients[0].get("/api/adverse-events", params={"limit": 500}).json()
    assert listed["total"] > 0
    assert {item["site_id"] for item in listed["items"]} == {investigators[0].site_id}


def test_a_site_scoped_user_only_sees_their_own_site_in_the_site_list(
    pi_clients, investigators, role_clients
):
    for client, person in zip(pi_clients, investigators):
        body = client.get("/api/sites").json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == person.site_id
    # Oversight roles see them all.
    assert role_clients[UserRole.REGULATOR.value].get("/api/sites").json()["total"] > 1


def test_oversight_roles_are_not_narrowed(role_clients):
    for role in (
        UserRole.SPONSOR.value,
        UserRole.REGULATOR.value,
        UserRole.ADMIN.value,
    ):
        body = role_clients[role].get("/api/subjects", params={"limit": 500}).json()
        assert len({item["site_id"] for item in body["items"]}) > 1, role


def test_an_investigator_with_no_site_sees_nothing_rather_than_everything(seeded_engine):
    """Fail closed.

    A site-scoped account whose site is missing is an inconsistency. The safe
    reading of "your site is unknown" is *no rows*, never *all rows*.
    """
    with Session(seeded_engine) as session:
        person = session.exec(
            select(User)
            .where(User.role == UserRole.PRINCIPAL_INVESTIGATOR.value)
            .order_by(User.id)
        ).first()
        orphan = User(
            email="orphan@example.test",
            full_name="Dr. No Site",
            role=UserRole.PRINCIPAL_INVESTIGATOR.value,
            site_id=None,
            hashed_password=person.hashed_password,
        )
        session.add(orphan)
        session.commit()
        session.refresh(orphan)
        orphan_id = orphan.id
        client = client_for(seeded_engine)
        client.headers["Authorization"] = f"Bearer {token_for_user(orphan)}"

    try:
        body = client.get("/api/subjects", params={"limit": 500}).json()
        assert body["total"] == 0
        assert body["items"] == []
    finally:
        with Session(seeded_engine) as session:
            session.delete(session.get(User, orphan_id))
            session.commit()


# ----------------------------------------------------------- the published matrix


def test_the_matrix_is_readable_without_a_token(anonymous_client):
    """It documents the rules; it does not expose anything the rules protect."""
    response = anonymous_client.get("/api/rbac-matrix")
    assert response.status_code == 200


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
        UserRole.PRINCIPAL_INVESTIGATOR.value,
        UserRole.COORDINATOR.value,
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
