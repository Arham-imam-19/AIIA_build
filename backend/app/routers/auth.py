"""Authentication endpoints: login, logout, who-am-i, and demo accounts.

Phase 2 added JWT authentication. An endpoint is protected by adding
`Depends(require(...))` - see `app/rbac.py` for how that is enforced.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import audit, config, security
from app.db import get_session
from app.enums import AuditAction, UserRole
from app.events import bus
from app.models import Trial, User
from app.rbac import (
    PERMISSION_LABELS,
    ROLE_LABELS,
    CurrentUser,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Roles the demo has a login for, ordered through the hierarchy.
DEMO_ROLE_ORDER = [
    UserRole.ADMIN.value,
    UserRole.INSTITUTION_ADMIN.value,
    UserRole.PRINCIPAL_INVESTIGATOR.value,
    UserRole.COORDINATOR.value,
    UserRole.SPONSOR.value,
    UserRole.ETHICS_COMMITTEE.value,
    UserRole.REGULATOR.value,
]


class LoginRequest(BaseModel):
    # Plain str, not pydantic's EmailStr: that would pull in the email-validator
    # package for no benefit here, since the only thing we do with the address is
    # look it up in the users table.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: "MePayload"


class MePayload(BaseModel):
    """Everything the frontend needs to draw the right dashboard.

    The permission list is sent along so the UI can hide a button the API would
    refuse anyway. The UI hiding it is a courtesy; the API refusing it is the
    actual security.
    """

    id: int
    email: str
    full_name: str
    role: str
    role_label: str
    site_id: int | None
    subject_id: int | None = None
    organization: str | None
    site_scoped: bool
    permissions: list[str]
    permission_labels: dict[str, str]


def _me(user: CurrentUser) -> MePayload:
    granted = sorted(p.value for p in user.permissions)
    return MePayload(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        role_label=user.role_label,
        site_id=user.site_id,
        subject_id=user.subject_id,
        organization=user.organization,
        site_scoped=user.is_site_scoped,
        permissions=granted,
        permission_labels={key: PERMISSION_LABELS.get(key, key) for key in granted},
    )


def _first_trial_id(session: Session) -> int | None:
    """The trial to attribute a login to. One trial exists in the demo dataset."""
    return session.exec(select(Trial.id).order_by(Trial.id)).first()


def _login_for_portal(
    body: LoginRequest,
    request: Request,
    session: Session,
    *,
    patient_portal: bool,
) -> LoginResponse:
    """Exchange valid credentials for a token only through the correct portal."""
    # Email is stored lower-case by the seed; compare case-insensitively so a
    # demo typed with a capital letter still works.
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()

    if (
        user is None
        or not security.verify_password(body.password, user.hashed_password)
        or (user.role == UserRole.PATIENT.value) != patient_portal
    ):
        # Log the attempt, then commit it - a failed login that leaves no trace is
        # exactly what an attacker would prefer.
        audit.record(
            session,
            user=None,
            user_email=email,
            action=AuditAction.LOGIN,
            entity_type="users",
            entity_label=email,
            reason="failed login: bad email or password",
            trial_id=_first_trial_id(session),
            request=request,
        )
        session.commit()
        # One message for both cases on purpose. "No such user" would let someone
        # discover which email addresses exist.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this account has been deactivated",
        )

    token, expires_at, _jti = security.create_access_token(
        user_id=user.id,  # type: ignore[arg-type]
        email=user.email,
        role=user.role,
        site_id=user.site_id,
        access_scope=user.access_scope,
    )

    current = CurrentUser(
        id=user.id,  # type: ignore[arg-type]
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        site_id=user.site_id,
        subject_id=user.subject_id,
        organization=user.organization,
        access_scope=user.access_scope,
    )

    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    audit.record(
        session,
        user=current,
        action=AuditAction.LOGIN,
        entity_type="users",
        entity_id=user.id,
        entity_label=user.email,
        reason="signed in",
        trial_id=_first_trial_id(session),
        request=request,
    )
    session.commit()

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=_me(current),
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Authenticate active clinical staff through the staff portal."""
    return _login_for_portal(body, request, session, patient_portal=False)


@router.post("/patient/login", response_model=LoginResponse)
def patient_login(
    body: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Authenticate active trial participants through the patient portal."""
    return _login_for_portal(body, request, session, patient_portal=True)


@router.post("/logout")
async def logout(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Revoke this token for the rest of its lifetime.

    Tells Redis to drop the session. Any open WebSocket sharing this token will
    receive a logout message and be closed.
    """
    if user.jti:
        await bus.revoke_token(user.jti)
    audit.record(
        session,
        user=user,
        action=AuditAction.LOGOUT,
        entity_type="users",
        entity_id=user.id,
        entity_label=user.email,
        reason="signed out",
        trial_id=_first_trial_id(session),
        request=request,
    )
    session.commit()
    return {"status": "signed out", "logged_out": True}


@router.get("/me", response_model=MePayload)
def me(user: CurrentUser = Depends(get_current_user)) -> MePayload:
    """Who is currently signed in, and what they are allowed to do.

    The frontend calls this on startup to restore a session from localStorage.
    If the token has expired, the 401 kicks them back to the login screen.
    """
    return _me(user)


def _demo_users_for_emails(session, emails: list[str]) -> dict:
    if not config.IS_DEVELOPMENT:
        raise HTTPException(status_code=404, detail="not found")

    users = session.exec(
        select(User).where(User.is_active == True).order_by(User.id)
    ).all()

    user_by_email = {u.email: u for u in users if u.hashed_password}
    
    selected_users = []
    for email in emails:
        if email in user_by_email:
            u = user_by_email[email]
            selected_users.append({
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "role_label": ROLE_LABELS.get(u.role, u.role),
                "site_id": u.site_id,
                "organization": u.organization,
                "access_scope": getattr(u, 'access_scope', 'GLOBAL'),
            })

    return {
        "password": config.DEMO_PASSWORD,
        "note": (
            "Synthetic demo accounts. All share one password so a five-minute "
            "pitch does not become a typing exercise."
        ),
        "users": selected_users,
        "seeded": len(selected_users) > 0,
        "hint": (
            "Empty? Run: docker compose exec backend python scripts/seed.py"
            if not selected_users
            else None
        ),
    }


@router.get("/demo-users")
def demo_users(session: Session = Depends(get_session)) -> dict:
    """List synthetic clinical-staff personas for the staff login page."""
    emails = [
        "meenakshi.sharma@demo.aiia-ctms.in",
        "kavita.nair@demo.aiia-ctms.in",
        "priya.raghavan@demo.aiia-ctms.in",
        "lalitha.krishnan@demo.aiia-ctms.in",
        "dr.gupta@demo.aiia-ctms.in",
        "director@demo.aiia-ctms.in",
        "investor@himalaya.com",
        "shri.arvind.kulkarni@demo.aiia-ctms.in",
        "dsmb.member@demo.aiia-ctms.in"
    ]
    return _demo_users_for_emails(session, emails)


@router.get("/patient/demo-users")
def patient_demo_users(session: Session = Depends(get_session)) -> dict:
    """List synthetic patient personas for the patient login page."""
    return _demo_users_for_emails(session, ["patient.01.014@demo.aiia-ctms.in"])


# Resolve the forward reference to MePayload now that it is defined.
LoginResponse.model_rebuild()
