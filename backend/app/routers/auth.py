"""Logging in and out.

**JWT (JSON Web Token)** in one sentence: a signed ID card the server hands you
at login, which the browser then shows with every request - like a festival
wristband, where staff trust the hologram instead of phoning the box office.

The flow:

    POST /api/auth/login      email + password  ->  token
    GET  /api/auth/me         token             ->  who you are, what you may do
    POST /api/auth/logout     token             ->  token is dead

Logging in and out are both written to the audit trail, including failed
attempts. In a regulated system "who was in the system, when" is part of the
record, not an operational detail.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import audit, config, security
from app.enums import AuditAction, UserRole
from app.events import bus
from app.models import Trial, User
from app.db import get_session
from app.rbac import (
    PERMISSION_LABELS,
    ROLE_LABELS,
    CurrentUser,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Roles the demo has a login for, in the order the pitch introduces them.
DEMO_ROLE_ORDER = [
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
        organization=user.organization,
        site_scoped=user.is_site_scoped,
        permissions=granted,
        permission_labels={key: PERMISSION_LABELS.get(key, key) for key in granted},
    )


def _first_trial_id(session: Session) -> int | None:
    """The trial to attribute a login to. One trial exists in the demo dataset."""
    return session.exec(select(Trial.id).order_by(Trial.id)).first()


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Exchange an email and password for a token."""
    # Email is stored lower-case by the seed; compare case-insensitively so a
    # demo typed with a capital letter still works.
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()

    if user is None or not security.verify_password(body.password, user.hashed_password):
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
    )

    current = CurrentUser(
        id=user.id,  # type: ignore[arg-type]
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        site_id=user.site_id,
        organization=user.organization,
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

    return LoginResponse(access_token=token, expires_at=expires_at, user=_me(current))


@router.get("/me", response_model=MePayload)
def me(user: CurrentUser = Depends(get_current_user)) -> MePayload:
    """Who the current token belongs to. The frontend calls this on page load to
    find out whether a saved token is still good."""
    return _me(user)


@router.post("/logout")
async def logout(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Revoke the current token.

    A JWT is self-contained, so the server cannot simply forget it - it has to
    remember that this particular one is no longer welcome. Its id goes on a deny
    list until the moment it would have expired anyway, after which there is
    nothing left to revoke. Like cancelling a keycard rather than changing every
    lock in the hotel.
    """
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

    if user.jti:
        await bus.revoke_token(user.jti, config.ACCESS_TOKEN_TTL_MINUTES * 60)
    return {"logged_out": True, "detail": "token revoked; log in again to continue"}


@router.get("/demo-users")
def demo_users(session: Session = Depends(get_session)) -> dict:
    """The five demo personas and the password they share.

    Development only. Printing credentials from an API would be indefensible in a
    real deployment, so this returns 404 unless APP_ENV=development - the same
    answer an attacker would get if the route did not exist.

    Every account here is synthetic. There is no real person and no real password
    anywhere in this system.
    """
    if not config.IS_DEVELOPMENT:
        raise HTTPException(status_code=404, detail="not found")

    users = session.exec(
        select(User).where(User.is_active == True).order_by(User.id)  # noqa: E712
    ).all()

    # One login per role: the first user found for each, matching what the seed
    # script prints. Site-scoped roles get several users (one per hospital), and
    # picking the lowest id makes "the demo PI" a stable choice.
    chosen: dict[str, User] = {}
    for user in users:
        if user.role in DEMO_ROLE_ORDER and user.role not in chosen:
            if user.hashed_password:
                chosen[user.role] = user

    return {
        "password": config.DEMO_PASSWORD,
        "note": (
            "Synthetic demo accounts. All five share one password so a five-minute "
            "pitch does not become a typing exercise."
        ),
        "users": [
            {
                "email": chosen[role].email,
                "full_name": chosen[role].full_name,
                "role": role,
                "role_label": ROLE_LABELS.get(role, role),
                "site_id": chosen[role].site_id,
                "organization": chosen[role].organization,
            }
            for role in DEMO_ROLE_ORDER
            if role in chosen
        ],
        "seeded": bool(chosen),
        "hint": (
            "Empty? Run: docker compose exec backend python scripts/seed.py"
            if not chosen
            else None
        ),
    }


# Resolve the forward reference to MePayload now that it is defined.
LoginResponse.model_rebuild()
