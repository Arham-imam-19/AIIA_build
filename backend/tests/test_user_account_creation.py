"""Tests for Primary Admin User Account Creation, Management, and Authentication."""

from sqlmodel import Session, select

from app.enums import UserRole
from app.models import Site, User
from tests.conftest import client_for


def test_admin_creates_and_authenticates_users_across_roles(seeded_engine):
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)

    with Session(seeded_engine) as session:
        site = session.exec(select(Site)).first()
        assert site is not None
        site_id = site.id

    roles_to_test = [
        (UserRole.PRINCIPAL_INVESTIGATOR.value, "Dr. Rajesh Sharma", "pi.rajesh@example.com", site_id),
        (UserRole.COORDINATOR.value, "Priya Nair", "coordinator.priya@example.com", site_id),
        (UserRole.ETHICS_COMMITTEE.value, "Prof. Anand Verma", "ethics.anand@example.com", None),
        (UserRole.SPONSOR.value, "Vikram Malhotra", "sponsor.vikram@example.com", None),
        (UserRole.REGULATOR.value, "Sunita Rao", "regulator.sunita@example.com", None),
        (UserRole.INSTITUTION_ADMIN.value, "Devendra Patil", "instadmin.devendra@example.com", site_id),
    ]

    for role, name, email, target_site_id in roles_to_test:
        payload = {
            "full_name": name,
            "email": email,
            "role": role,
            "password": "SecurePassword123!",
            "site_id": target_site_id,
            "organization": "AIIA Research Institute",
            "phone": "+91 98765 00000",
        }
        res = admin_client.post("/api/users", json=payload)
        assert res.status_code == 201, f"Failed for role {role}: {res.text}"
        user_data = res.json()
        assert user_data["email"] == email.lower()
        assert user_data["role"] == role
        assert user_data["is_active"] is True

        # Test login with the newly created account credentials
        login_res = admin_client.post(
            "/api/auth/login",
            json={"email": email, "password": "SecurePassword123!"},
        )
        assert login_res.status_code == 200, f"Login failed for {email}: {login_res.text}"
        login_data = login_res.json()
        assert "access_token" in login_data
        assert login_data["user"]["email"] == email.lower()
        assert login_data["user"]["role"] == role


def test_admin_updates_and_deactivates_user_account(seeded_engine):
    admin_client = client_for(seeded_engine, UserRole.ADMIN.value)

    # 1. Create user
    payload = {
        "full_name": "Temporary Coordinator",
        "email": "temp.coord@example.com",
        "role": UserRole.COORDINATOR.value,
        "password": "Password123!",
    }
    create_res = admin_client.post("/api/users", json=payload)
    assert create_res.status_code == 201
    user_id = create_res.json()["id"]

    # 2. Deactivate user
    patch_res = admin_client.patch(
        f"/api/users/{user_id}",
        json={"is_active": False, "phone": "+91 99999 11111"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    # 3. Attempt login with deactivated user -> expect 403
    login_res = admin_client.post(
        "/api/auth/login",
        json={"email": "temp.coord@example.com", "password": "Password123!"},
    )
    assert login_res.status_code == 403
    assert "deactivated" in login_res.json()["detail"].lower()
