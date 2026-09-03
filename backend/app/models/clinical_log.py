"""Clinical progress and nursing log entries for trial participants."""

from datetime import datetime
from sqlmodel import Field, SQLModel
from app.models.base import utcnow


class ClinicalLogEntry(SQLModel, table=True):
    """An append-only clinical progress note or observation for a participant.

    In compliance with ALCOA+ and GCP principles, clinical log entries are
    strictly immutable (append-only), timestamped server-side, and attributed
    to the authenticated session user.
    """

    __tablename__ = "clinical_log_entries"

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)
    site_id: int = Field(foreign_key="sites.id", index=True)

    # Controlled categories:
    # 'medication_administered', 'symptom_reported', 'vital_sign', 'adverse_event', 'general_note'
    entry_type: str = Field(max_length=50, index=True)

    # Medication / Substance administration (if applicable)
    substance_name: str | None = Field(default=None, max_length=200)
    dose: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=50)

    # Symptom / Observation / Clinical Narrative
    observation_description: str = Field(max_length=4000)

    # Optional linked visit
    linked_visit_id: int | None = Field(default=None, foreign_key="visits.id", index=True)

    # Optional linked Adverse Event if escalated to Pharmacovigilance
    linked_ae_id: int | None = Field(default=None, foreign_key="adverse_events.id", index=True)

    # ALCOA+ Append-Only Correction mechanism
    correction_of_entry_id: int | None = Field(default=None, foreign_key="clinical_log_entries.id", index=True)
    correction_reason: str | None = Field(default=None, max_length=500)

    # Server-stamped audit provenance
    entered_by_user_id: int = Field(foreign_key="users.id", index=True)
    entered_by_name: str = Field(max_length=120)
    timestamp: datetime = Field(default_factory=utcnow, index=True)
