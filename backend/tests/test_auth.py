"""Phase 2: logging in, staying logged in, and being turned away.

A **JWT** is a signed ID card the server hands you at login: it says "user 7,
sponsor, expires at 6pm" and carries a signature only this server can produce.
These tests check the card is issued correctly, checked properly, and can be
cancelled.

The one deliberate design decision worth stating: a failed login is written to
the audit trail *before* the 401 goes out. A failed sign-in that leaves no trace
is exactly what an attacker would prefer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlmodel import Session, select

from app import config, security
from app.enums import UserRole
from app.models import AuditLog, User

DEMO_PASSWORD = config.DEMO_PASSWORD


@pytest.fixture(scope="module")
def personas(seeded_engine) -> dict[str, str]:
    """One email per role, as the demo would use."""
    with Session(seeded_engine) as session:
        users = session.exec(select(User).order_by(User.id)).all()
    chosen: dict[str, str] = {}
    for user in users:
        chosen.setdefault(user.role, user.email)
    return chosen


# ------------------------------------------------------------------ the seed


def test_every_seeded_user_has_a_password_hash_and_never_the_password(seeded_engine):
    """The database stores a one-way scramble, not what anyone typed."""
    with Session(seeded_engine) as session:
        users = session.exec(select(User)).all()
    assert users
    for user in users:
        assert user.hashed_password, f"{user.email} has no password"
        assert user.hashed_password != DEMO_PASSWORD
        # bcrypt hashes are self-describing: cost factor and salt up front.
        assert user.hashed_password.startswith("$2")


def test_the_five_demo_personas_can_all_log_in(client, personas):
    for role in (
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
        UserRole.SPONSOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.REGULATOR,
    ):
        email = personas[role.value]
        response = client.post(
            "/api/auth/login", json={"email": email, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200, f"{role.value}: {response.text}"
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["role"] == role.value
        assert body["user"]["email"] == email


def test_demo_users_endpoint_lists_one_login_per_role(client):
    body = client.get("/api/auth/demo-users").json()
    assert body["seeded"] is True
    assert body["password"] == DEMO_PASSWORD
    roles = [user["role"] for user in body["users"]]
    assert len(roles) == len(set(roles)), "a role appeared twice"
    for role in ("principal_investigator", "coordinator", "sponsor", "ethics_committee",
                 "regulator"):
        assert role in roles


def test_demo_users_never_returns_a_hash(client):
    body = client.get("/api/auth/demo-users").json()
    for user in body["users"]:
        assert not [key for key in user if "password" in key.lower()]


# ---------------------------------------------------------------- the token


def test_login_token_carries_the_role_and_site_but_no_password(client, personas):
    body = client.post(
        "/api/auth/login",
        json={"email": personas["principal_investigator"], "password": DEMO_PASSWORD},
    ).json()
    claims = security.decode_access_token(body["access_token"])
    assert claims["role"] == "principal_investigator"
    assert claims["site_id"] is not None, "an investigator's token must name their site"
    assert claims["jti"], "every token needs its own id so logout can revoke it"
    # A JWT is signed, not encrypted - anyone can read it, so nothing secret goes in.
    assert not [key for key in claims if "password" in key.lower()]


def test_me_describes_the_holder_of_the_token(client, personas):
    login = client.post(
        "/api/auth/login",
        json={"email": personas["ethics_committee"], "password": DEMO_PASSWORD},
    ).json()
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    ).json()
    assert me["role"] == "ethics_committee"
    assert me["role_label"] == "Ethics Committee"
    assert me["site_scoped"] is False
    # The UI renders these, so they have to arrive with the identity.
    assert "ae:read" in me["permissions"]
    assert "subject:read" not in me["permissions"]
    assert me["permission_labels"]["ae:read"] == "View adverse events"


def test_me_without_a_token_says_how_to_get_one(anonymous_client):
    response = anonymous_client.get("/api/auth/me")
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert "/api/auth/login" in detail
    assert "Bearer" in detail
    # And the header that tells an API client what to do.
    assert response.headers.get("www-authenticate") == "Bearer"


# ------------------------------------------------------------- failed logins


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "nobody@example.test", "password": DEMO_PASSWORD},
        {"email": "PLACEHOLDER", "password": "not-the-password"},
    ],
)
def test_bad_credentials_are_one_indistinguishable_401(client, personas, payload):
    """"No such user" would let someone discover which emails exist."""
    if payload["email"] == "PLACEHOLDER":
        payload = {**payload, "email": personas["sponsor"]}
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "incorrect email or password"


def test_a_failed_login_is_recorded_in_the_audit_trail(client, seeded_engine):
    email = "intruder@example.test"
    client.post("/api/auth/login", json={"email": email, "password": "guess"})

    with Session(seeded_engine) as session:
        entry = session.exec(
            select(AuditLog)
            .where(AuditLog.entity_label == email)
            .order_by(AuditLog.id.desc())
        ).first()
    assert entry is not None, "a failed login left no trace"
    assert entry.action == "login"
    assert "failed login" in entry.reason
    assert entry.user_id is None, "there is no user to attribute it to"


def test_email_is_matched_case_insensitively(client, personas):
    """A demo typed with a capital letter still has to work."""
    email = personas["sponsor"]
    response = client.post(
        "/api/auth/login", json={"email": email.upper(), "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200


def test_password_comparison_is_not_a_prefix_match(client, personas):
    response = client.post(
        "/api/auth/login",
        json={"email": personas["sponsor"], "password": DEMO_PASSWORD[:-1]},
    )
    assert response.status_code == 401


# ------------------------------------------------------- rejected tokens


@pytest.mark.parametrize(
    "token, expected",
    [
        ("not-a-token", "invalid token"),
        ("", "not signed in"),
    ],
)
def test_a_malformed_token_is_refused_with_a_reason(anonymous_client, token, expected):
    response = anonymous_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert expected in response.json()["detail"]


def test_an_expired_token_is_refused(client, seeded_engine):
    """Backdated by an hour with a one-minute life, so it is already stale."""
    with Session(seeded_engine) as session:
        user = session.exec(select(User).order_by(User.id)).first()
        token, _expires, _jti = security.create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
            site_id=user.site_id,
            ttl_minutes=-60,
        )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


def test_a_token_signed_with_another_key_is_refused(client, seeded_engine):
    """The signature is the whole point: a forged card must not open the door."""
    with Session(seeded_engine) as session:
        user = session.exec(select(User).order_by(User.id)).first()
        user_id, user_email = user.id, user.email
    forged = jwt.encode(
        {
            "sub": str(user_id),
            "email": user_email,
            "role": UserRole.ADMIN.value,  # promoting themselves, too
            "site_id": None,
            "jti": "forged",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        "not-the-real-secret",
        algorithm=config.JWT_ALGORITHM,
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_a_token_for_a_deleted_user_is_refused(client):
    """The token is trusted for its signature; the database is still the authority."""
    token, _expires, _jti = security.create_access_token(
        user_id=999_999, email="ghost@example.test", role=UserRole.ADMIN.value, site_id=None
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "no longer exists" in response.json()["detail"]


def test_a_deactivated_account_stops_working_before_its_token_expires(
    client, seeded_engine
):
    """Someone removed from the study must not keep working for twelve hours."""
    with Session(seeded_engine) as session:
        user = session.exec(
            select(User).where(User.role == UserRole.COORDINATOR.value).order_by(User.id)
        ).first()
        user_id = user.id
        token, _expires, _jti = security.create_access_token(
            user_id=user.id, email=user.email, role=user.role, site_id=user.site_id
        )
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/auth/me", headers=headers).status_code == 200

        user.is_active = False
        session.add(user)
        session.commit()

    try:
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
        assert "deactivated" in response.json()["detail"]
    finally:
        # Put them back: this database is shared by the rest of the module.
        with Session(seeded_engine) as session:
            restored = session.get(User, user_id)
            restored.is_active = True
            session.add(restored)
            session.commit()


# -------------------------------------------------------------------- logout


def test_logout_revokes_that_token_and_only_that_token(client, personas):
    """Cancel one keycard, do not rekey the hotel."""
    first = client.post(
        "/api/auth/login",
        json={"email": personas["regulator"], "password": DEMO_PASSWORD},
    ).json()["access_token"]
    second = client.post(
        "/api/auth/login",
        json={"email": personas["regulator"], "password": DEMO_PASSWORD},
    ).json()["access_token"]
    assert first != second, "each login must mint its own token"

    out = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {first}"})
    assert out.status_code == 200
    assert out.json()["logged_out"] is True

    dead = client.get("/api/auth/me", headers={"Authorization": f"Bearer {first}"})
    assert dead.status_code == 401
    assert "logged out" in dead.json()["detail"]

    # The other session - the same person on their phone - is untouched.
    alive = client.get("/api/auth/me", headers={"Authorization": f"Bearer {second}"})
    assert alive.status_code == 200


def test_logout_is_recorded_in_the_audit_trail(client, personas, seeded_engine):
    token = client.post(
        "/api/auth/login",
        json={"email": personas["coordinator"], "password": DEMO_PASSWORD},
    ).json()["access_token"]
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    with Session(seeded_engine) as session:
        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "logout").order_by(AuditLog.id.desc())
        ).first()
    assert entry is not None
    assert entry.user_email == personas["coordinator"]


# ------------------------------------------------- the un-seeded database


def test_demo_users_on_an_empty_database_tells_you_to_seed(empty_client):
    body = empty_client.get("/api/auth/demo-users").json()
    assert body["seeded"] is False
    assert body["users"] == []
    assert "seed.py" in body["hint"]


def test_login_on_an_empty_database_is_a_401_not_a_crash(empty_client):
    """No users exist, so nobody can sign in - but politely."""
    response = empty_client.post(
        "/api/auth/login", json={"email": "anyone@example.test", "password": "x"}
    )
    assert response.status_code == 401
