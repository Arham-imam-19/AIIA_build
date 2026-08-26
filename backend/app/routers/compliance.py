"""The audit trail, plus the users it refers to.

An audit trail answers "who changed what, when, and why" for every record. The
rule (21 CFR Part 11, the regulation regulators cite for electronic records) is
that it is append-only: entries are added, never edited or deleted. Like a bank
statement - a mistaken payment is corrected by a second entry, not by erasing the
first.

So there is deliberately no PUT or DELETE in this file, and there never should
be. Phase 5 adds the e-signature and compliance-scoring endpoints alongside it.

Phase 2 access: only the Ethics Committee, the Regulator and an admin may read the
audit trail. An investigator cannot audit themselves, which is the point of an
independent trail.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, SQLModel, or_, select

from app.db import get_session
from app.models import AuditLog, User
from app.rbac import CurrentUser, Permission, require
from app.routers.common import Page, limit_param, offset_param, paginate

router = APIRouter(prefix="/api", tags=["compliance"])


@router.get("/audit-log", response_model=Page[AuditLog])
def list_audit_log(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AUDIT_READ)),
    trial_id: int | None = Query(None),
    user_id: int | None = Query(None),
    action: str | None = Query(None, description="create, update, approve, sign..."),
    entity_type: str | None = Query(None, description="e.g. subjects, adverse_events"),
    entity_id: int | None = Query(None),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[AuditLog]:
    # Most recent first, which is how an audit view is always read.
    statement = select(AuditLog).order_by(AuditLog.timestamp.desc())  # type: ignore[union-attr]
    if trial_id is not None:
        statement = statement.where(AuditLog.trial_id == trial_id)
    if user_id is not None:
        statement = statement.where(AuditLog.user_id == user_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(AuditLog.entity_id == entity_id)
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


class UserPublic(SQLModel):
    """A user as the API returns them: everything except the password hash.

    `User` doubles as the database table and the API shape, which is convenient
    right up to the moment a column exists that must never leave the server. Now
    that Phase 2 has filled `hashed_password` in, listing users returns this
    instead - and `test_users_never_expose_a_password` keeps it that way.
    """

    id: int
    email: str
    full_name: str
    role: str
    site_id: int | None = None
    organization: str | None = None
    phone: str | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


@router.get("/users", response_model=Page[UserPublic])
def list_users(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.USER_READ)),
    role: str | None = Query(None, description="one of the five personas, or admin"),
    site_id: int | None = Query(None),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[UserPublic]:
    """The study personnel.

    Site scoping is slightly looser here than elsewhere, on purpose: an
    investigator sees their own site's staff *plus* the trial-wide people (sponsor,
    ethics committee, regulator, admin), who have no site of their own. Hiding the
    sponsor from the investigator running the study would be scoping for its own
    sake rather than for confidentiality.
    """
    statement = select(User).order_by(User.role, User.full_name)
    if role:
        statement = statement.where(User.role == role)
    if site_id is not None:
        statement = statement.where(User.site_id == site_id)
    scope = user.scope_site_id
    if scope is not None:
        statement = statement.where(
            or_(User.site_id == scope, User.site_id.is_(None))  # type: ignore[union-attr]
        )
    total, items = paginate(session, statement, limit, offset)
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[UserPublic.model_validate(u, from_attributes=True) for u in items],
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
