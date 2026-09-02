"""The audit trail - append-only, never edited.

Regulators (21 CFR Part 11, and GCP generally) require that every change to
trial data leaves a trace: who changed what, from what to what, when, and why.
The point is that data cannot be quietly rewritten after the fact.

The rule this table lives by: **rows are only ever inserted.** There is no code
path anywhere in this project that updates or deletes an AuditLog row, and none
should ever be added. A correction is a new row, the way a bank statement
records a reversing entry rather than erasing the original line.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class AuditLog(SQLModel, table=True):
    """One recorded action. Insert-only."""

    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)

    timestamp: datetime = Field(default_factory=utcnow, index=True)

    # Who did it. The user id is kept for joins, but email and role are also
    # copied in as plain text on purpose: if the user record is later changed or
    # removed, the log must still say who acted. An audit trail that depends on
    # another table staying intact is not an audit trail.
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    user_email: str | None = Field(default=None, max_length=255)
    user_role: str | None = Field(default=None, max_length=40)

    # One of enums.AuditAction.
    action: str = Field(max_length=30, index=True)

    # Which record was touched: the table name and its primary key,
    # e.g. ("adverse_events", 42). Stored loosely rather than as a foreign key so
    # that one log table can cover every entity in the system.
    entity_type: str = Field(max_length=60, index=True)
    entity_id: int | None = Field(default=None, index=True)
    entity_label: str | None = Field(default=None, max_length=200)

    # For an UPDATE, exactly what changed. Values are stored as text so any field
    # type can be logged through the same columns.
    field_name: str | None = Field(default=None, max_length=100)
    old_value: str | None = Field(default=None, max_length=2000)
    new_value: str | None = Field(default=None, max_length=2000)

    # GCP expects a reason for changing trial data after it was first entered.
    reason: str | None = Field(default=None, max_length=1000)

    # Context, for tracing a session end to end.
    trial_id: int | None = Field(default=None, foreign_key="trials.id", index=True)
    ip_address: str | None = Field(default=None, max_length=60)
    user_agent: str | None = Field(default=None, max_length=300)

# Blockchain-lite: cryptographic hashes to prove immutability
    previous_hash: str | None = Field(default=None, max_length=64)
    current_hash: str | None = Field(default=None, max_length=64, index=True)

    created_at: datetime = Field(default_factory=utcnow)
