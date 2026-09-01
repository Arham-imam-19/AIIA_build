"""Compliance, audit trail, and study personnel listings."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, SQLModel, select

from app.db import get_session
from app.models import AuditLog, User
from app.rbac import CurrentUser, Permission, require, scoped
from app.routers.common import Page, limit_param, offset_param, paginate

router = APIRouter(prefix="/api", tags=["compliance"])


# Pydantic schema for returning AuditLog rows without leaking raw internals.
class AuditLogPublic(SQLModel):
    id: int
    timestamp: datetime
    user_email: str | None
    user_role: str | None
    action: str
    entity_type: str
    entity_id: int | None
    entity_label: str | None
    field_name: str | None
    old_value: str | None
    new_value: str | None
    reason: str
    ip_address: str | None
    user_agent: str | None


class UserPublic(SQLModel):
    id: int
    email: str
    full_name: str
    role: str
    site_id: int | None
    organization: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


@router.get("/audit-log", response_model=Page[AuditLogPublic])
def list_audit_log(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AUDIT_READ)),
    entity_type: str | None = Query(None, description="filter by entity type"),
    action: str | None = Query(None, description="filter by action"),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[AuditLogPublic]:
    """The 21 CFR Part 11 audit trail.

    Append-only. Visible only to oversight roles (Ethics Committee, Regulator,
    Admin). It is never filtered by site: a regulator inspecting the trial needs
    the complete timeline.
    """
    statement = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
    if action:
        statement = statement.where(AuditLog.action == action)
    total, items = paginate(session, statement, limit, offset)
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[AuditLogPublic.model_validate(item, from_attributes=True) for item in items],
    )


@router.get("/users", response_model=Page[UserPublic])
def list_users(
    session: Session = Depends(get_session),
    caller: CurrentUser = Depends(require(Permission.USER_READ)),
    role: str | None = Query(None, description="filter by role"),
    site_id: int | None = Query(None, description="filter by site"),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[UserPublic]:
    """Study personnel.

    Site-scoped callers see only people at their own hospital. Passwords are
    never returned - see `UserPublic` above.
    """
    statement = select(User).order_by(User.full_name)
    if role:
        statement = statement.where(User.role == role)
    if site_id is not None:
        statement = statement.where(User.site_id == site_id)
    statement = scoped(statement, User.site_id, caller)
    total, items = paginate(session, statement, limit, offset)
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[UserPublic.model_validate(item, from_attributes=True) for item in items],
    )


@router.get("/users/{user_id}", response_model=UserPublic)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    caller: CurrentUser = Depends(require(Permission.USER_READ)),
) -> UserPublic:
    found = session.get(User, user_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"no user with id {user_id}")
    scope = caller.scope_site_id
    if scope is not None and found.site_id is not None and found.site_id != scope:
        raise HTTPException(
            status_code=403,
            detail=(
                f"this user belongs to another site. {caller.role_label} access is "
                f"limited to site id {caller.site_id}."
            ),
        )
    return UserPublic.model_validate(found, from_attributes=True)


class CreateUserRequest(SQLModel):
    email: str
    full_name: str
    role: str
    password: str = "aiia2026"
    site_id: int | None = None
    organization: str | None = None
    phone: str | None = None


@router.post("/users", response_model=UserPublic, status_code=201)
def create_user(
    body: CreateUserRequest,
    session: Session = Depends(get_session),
    caller: CurrentUser = Depends(require(Permission.USER_MANAGE)),
) -> UserPublic:
    """Add a new user (Primary Admin adds Institution Admins; Institution Admin adds Researchers)."""
    from app import security

    email = body.email.strip().lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"email {email} already in use")

    # If caller is site-scoped (Institution Admin), enforce site_id
    target_site_id = caller.site_id if caller.is_site_scoped else body.site_id

    new_user = User(
        email=email,
        full_name=body.full_name,
        role=body.role,
        hashed_password=security.hash_password(body.password),
        site_id=target_site_id,
        organization=body.organization,
        phone=body.phone,
        is_active=True,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return UserPublic.model_validate(new_user, from_attributes=True)
