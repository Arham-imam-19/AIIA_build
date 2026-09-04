"""Data and Safety Monitoring Board (DSMB) directives and decisions."""

from datetime import datetime
from sqlmodel import Field, SQLModel
from app.models.base import utcnow


class DsmbDecision(SQLModel, table=True):
    """An official safety determination and directive issued by the DSMB."""

    __tablename__ = "dsmb_decisions"

    id: int | None = Field(default=None, primary_key=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)
    site_id: int | None = Field(default=None, foreign_key="sites.id", index=True, nullable=True)

    # One of 'CONTINUE', 'MODIFY', 'HALT'
    decision: str = Field(max_length=40, index=True)
    directive_title: str | None = Field(default=None, max_length=255)
    notes: str = Field(max_length=4000)
    recommended_action: str | None = Field(default=None, max_length=500)

    # Originator provenance
    created_by_user_id: int = Field(foreign_key="users.id", index=True)
    created_by_name: str = Field(max_length=150)
    created_at: datetime = Field(default_factory=utcnow, index=True)

    # Principal Investigator acknowledgment
    acknowledged_at: datetime | None = Field(default=None)
    acknowledged_by_user_id: int | None = Field(default=None, foreign_key="users.id", nullable=True)
    acknowledged_by_name: str | None = Field(default=None, max_length=150)
