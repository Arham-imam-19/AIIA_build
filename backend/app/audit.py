"""One place that writes audit entries, so every write is logged the same way.

The audit trail is append-only (see `app/models/audit.py`). This module only ever
INSERTs, and nothing here updates or deletes a row.

Why a helper instead of constructing `AuditLog(...)` at each call site: three
fields must be filled in consistently every single time - the acting user's email
and role copied in as text, and the request's IP and browser. Forgetting them
produces an entry that is technically present and useless in an inspection.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request
import hashlib
from sqlmodel import Session, select

from app.enums import AuditAction
from app.models import AuditLog
from app.rbac import CurrentUser


def _client_ip(request: Request | None) -> str | None:
    """The caller's address, allowing for one proxy in front of us.

    Behind the Vite dev server every request appears to come from the container
    network, so X-Forwarded-For is what actually identifies the browser.
    """
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:60]
    return request.client.host[:60] if request.client else None


def record(
    session: Session,
    *,
    user: CurrentUser | None,
    action: AuditAction,
    entity_type: str,
    entity_id: int | None = None,
    entity_label: str | None = None,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    reason: str | None = None,
    trial_id: int | None = None,
    request: Request | None = None,
    user_email: str | None = None,
    user_role: str | None = None,
) -> AuditLog:
    """Add one audit entry to the session. The caller commits.

    Adding rather than committing is deliberate: the entry and the change it
    describes must land in the same transaction, so it is impossible to have one
    without the other.

    `user_email` / `user_role` exist for the failed-login case, where there is no
    authenticated user but the attempt still has to be recorded.
    """
    last_log = session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    prev_hash = last_log.current_hash if last_log and last_log.current_hash else "0" * 64

    entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        user_id=user.id if user else None,
        user_email=(user.email if user else user_email),
        user_role=(user.role if user else user_role),
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label[:200] if entity_label else None,
        field_name=field_name,
        old_value=str(old_value)[:2000] if old_value is not None else None,
        new_value=str(new_value)[:2000] if new_value is not None else None,
        reason=reason[:1000] if reason else None,
        trial_id=trial_id,
        ip_address=_client_ip(request),
        user_agent=(
            request.headers.get("user-agent", "")[:300] if request is not None else None
        ),
        previous_hash=prev_hash,
    )
    
    # Calculate deterministic hash of the entry
    payload = f"{prev_hash}|{entry.timestamp.isoformat()}|{entry.action}|{entry.user_email}|{entry.entity_type}|{entry.entity_id}|{entry.new_value}"
    entry.current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    session.add(entry)
    return entry
