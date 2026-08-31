"""Compliance, audit trail, and study personnel listings."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import Session, SQLModel, select

from app.db import get_session
from app.enums import UserRole
from app.models import AuditLog, User
from app.rbac import CurrentUser, Permission, require, scoped
from app.routers.common import Page, limit_param, offset_param, paginate
from app.services import privacy

router = APIRouter(prefix="/api", tags=["compliance"])


# Pydantic schema for returning AuditLog rows without leaking raw internals.
class AuditLogPublic(SQLModel):
    id: int
    timestamp: datetime
    user_id: int | None = None
    user_email: str | None
    user_role: str | None
    action: str
    entity_type: str
    entity_id: int | None
    entity_label: str | None
    field_name: str | None
    old_value: str | None
    new_value: str | None
    reason: str | None
    trial_id: int | None = None
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
    trial_id: int | None = Query(None, description="filter by trial id"),
    start_date: date | None = Query(None, description="filter events on or after this date"),
    end_date: date | None = Query(None, description="filter events on or before this date"),
    search: str | None = Query(None, description="search in user email, label, reason, or field"),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[AuditLogPublic]:
    """The 21 CFR Part 11 ALCOA+ audit trail.

    Append-only. Visible only to oversight roles (Ethics Committee, Regulator, Admin).
    It is never filtered by site: a regulator inspecting the trial needs the complete timeline.
    """
    statement = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
    if action:
        statement = statement.where(AuditLog.action == action)
    if trial_id is not None:
        statement = statement.where(AuditLog.trial_id == trial_id)
    if start_date is not None:
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        statement = statement.where(AuditLog.timestamp >= start_dt)
    if end_date is not None:
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        statement = statement.where(AuditLog.timestamp <= end_dt)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                AuditLog.user_email.ilike(term),  # type: ignore[union-attr]
                AuditLog.entity_label.ilike(term),  # type: ignore[union-attr]
                AuditLog.reason.ilike(term),  # type: ignore[union-attr]
                AuditLog.field_name.ilike(term),  # type: ignore[union-attr]
            )
        )

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
    never returned. Patient accounts are minimized for non-site callers under DPDP Act 2023.
    """
    statement = select(User).order_by(User.full_name)
    if role:
        statement = statement.where(User.role == role)
    if site_id is not None:
        statement = statement.where(User.site_id == site_id)
    statement = scoped(statement, User.site_id, caller)
    total, items = paginate(session, statement, limit, offset)

    sanitized_items = []
    for item in items:
        # Check data minimization for patient roles
        if item.role == UserRole.PATIENT.value and privacy.should_mask_patient_pii(caller, item.site_id):
            sanitized_items.append(
                UserPublic(
                    id=item.id,  # type: ignore[arg-type]
                    email=privacy.mask_email(item.email) or item.email,
                    full_name=privacy.mask_patient_name(item.full_name),
                    role=item.role,
                    site_id=item.site_id,
                    organization=item.organization,
                    phone=privacy.mask_phone(item.phone),
                    is_active=item.is_active,
                    created_at=item.created_at,
                    last_login_at=item.last_login_at,
                )
            )
        else:
            sanitized_items.append(UserPublic.model_validate(item, from_attributes=True))

    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=sanitized_items,
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

    if found.role == UserRole.PATIENT.value and privacy.should_mask_patient_pii(caller, found.site_id):
        return UserPublic(
            id=found.id,  # type: ignore[arg-type]
            email=privacy.mask_email(found.email) or found.email,
            full_name=privacy.mask_patient_name(found.full_name),
            role=found.role,
            site_id=found.site_id,
            organization=found.organization,
            phone=privacy.mask_phone(found.phone),
            is_active=found.is_active,
            created_at=found.created_at,
            last_login_at=found.last_login_at,
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
