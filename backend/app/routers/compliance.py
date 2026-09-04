"""Compliance, audit trail, and study personnel listings."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import Session, SQLModel, select

from app import audit
from app.db import get_session
from app.enums import AuditAction, UserRole
from app.models import AuditLog, User
from app.rbac import CurrentUser, Permission, require, scoped
from app.routers.common import Page, limit_param, offset_param, paginate
from app.services import privacy

router = APIRouter(prefix="/api", tags=["compliance"])


# Pydantic schema for returning AuditLog rows without leaking raw internals.
class AuditLogPublic(SQLModel):
    id: int
    timestamp: datetime
    timestamp_ist: str | None = None
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
    """The 21 CFR Part 11 & CERT-In ALCOA+ audit trail.

    Append-only. Visible only to oversight roles (Ethics Committee, Regulator, Admin).
    Preserves records with dual UTC and Indian Standard Time (IST / UTC+05:30) stamps.
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
    from datetime import timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    sanitized_items = []
    for item in items:
        dto = AuditLogPublic.model_validate(item, from_attributes=True)
        dt = item.timestamp if item.timestamp.tzinfo else item.timestamp.replace(tzinfo=timezone.utc)
        dto.timestamp_ist = dt.astimezone(ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        sanitized_items.append(dto)

    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=sanitized_items,
    )


@router.get("/users", response_model=Page[UserPublic])
def list_users(
    session: Session = Depends(get_session),
    caller: CurrentUser = Depends(require(Permission.USER_READ)),
    role: str | None = Query(None, description="filter by role"),
    site_id: int | None = Query(None, description="filter by site"),
    search: str | None = Query(None, description="search by name or email"),
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
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                User.full_name.ilike(term),  # type: ignore[union-attr]
                User.email.ilike(term),  # type: ignore[union-attr]
            )
        )
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
    password: str = "AIIA@2026!"
    site_id: int | None = None
    organization: str | None = None
    phone: str | None = None


class UpdateUserRequest(SQLModel):
    full_name: str | None = None
    phone: str | None = None
    organization: str | None = None
    is_active: bool | None = None
    password: str | None = None
    site_id: int | None = None


@router.post("/users", response_model=UserPublic, status_code=201)
def create_user(
    body: CreateUserRequest,
    session: Session = Depends(get_session),
    caller: CurrentUser = Depends(require(Permission.USER_MANAGE)),
) -> UserPublic:
    """Add a new user (Primary Admin adds all roles; Institution Admin adds site researchers)."""
    from app import security

    email = body.email.strip().lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"email {email} already in use")

    # If caller is site-scoped (Institution Admin), enforce site_id
    target_site_id = caller.site_id if caller.is_site_scoped else body.site_id

    new_user = User(
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        hashed_password=security.hash_password(body.password),
        site_id=target_site_id,
        organization=body.organization.strip() if body.organization else None,
        phone=body.phone.strip() if body.phone else None,
        is_active=True,
    )
    session.add(new_user)
    session.flush()

    audit.record(
        session,
        user=caller,
        action=AuditAction.CREATE,
        entity_type="users",
        entity_id=new_user.id,
        entity_label=new_user.email,
        reason=f"Account created for {new_user.full_name} with role {new_user.role}",
    )
    session.commit()
    session.refresh(new_user)
    return UserPublic.model_validate(new_user, from_attributes=True)


@router.patch("/users/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    session: Session = Depends(get_session),
    caller: CurrentUser = Depends(require(Permission.USER_MANAGE)),
) -> UserPublic:
    """Update user account status, credentials, or profile information."""
    from app import security

    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail=f"no user with id {user_id}")

    scope = caller.scope_site_id
    if scope is not None and target_user.site_id is not None and target_user.site_id != scope:
        raise HTTPException(
            status_code=403,
            detail=f"forbidden: caller site {scope} cannot modify user at site {target_user.site_id}",
        )

    if body.full_name is not None:
        target_user.full_name = body.full_name.strip()
    if body.phone is not None:
        target_user.phone = body.phone.strip() if body.phone else None
    if body.organization is not None:
        target_user.organization = body.organization.strip() if body.organization else None
    if body.is_active is not None:
        old_active = target_user.is_active
        target_user.is_active = body.is_active
        audit.record(
            session,
            user=caller,
            action=AuditAction.UPDATE,
            entity_type="users",
            entity_id=target_user.id,
            entity_label=target_user.email,
            field_name="is_active",
            old_value=str(old_active),
            new_value=str(body.is_active),
            reason=f"Account {'activated' if body.is_active else 'deactivated'} by {caller.role_label}",
        )
    if body.password:
        target_user.hashed_password = security.hash_password(body.password)
        audit.record(
            session,
            user=caller,
            action=AuditAction.UPDATE,
            entity_type="users",
            entity_id=target_user.id,
            entity_label=target_user.email,
            field_name="password",
            reason=f"Password reset by {caller.role_label}",
        )
    if body.site_id is not None and not caller.is_site_scoped:
        target_user.site_id = body.site_id

    session.add(target_user)
    session.commit()
    session.refresh(target_user)
    return UserPublic.model_validate(target_user, from_attributes=True)
