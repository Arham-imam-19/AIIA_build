"""Trial participants, de-identified."""

from datetime import date, datetime

from sqlmodel import Field, SQLModel, Column
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import utcnow


class Subject(SQLModel, table=True):
    """One trial participant.

    Deliberately de-identified: there is no name, no address, no phone number
    and no date of birth - only a year of birth and an age. A subject is known
    by their subject code, which is how real trial databases work, so that data
    can be shared and audited without exposing who the person is.

    (This project uses only synthetic participants regardless. The design still
    follows the real rule, because the demo is meant to show a system that could
    hold real data safely.)
    """

    __tablename__ = "subjects"

    id: int | None = Field(default=None, primary_key=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)
    site_id: int = Field(foreign_key="sites.id", index=True)

    # The participant's public identifier, e.g. "AIIA-ASH-01-014".
    subject_code: str = Field(max_length=60, unique=True, index=True)

    # Lead researcher (PI or Coordinator) managing this participant.
    assigned_researcher_id: int | None = Field(
        default=None, foreign_key="users.id", index=True
    )
    # Linked user login account for the patient portal, if created.
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)

    # One of enums.SubjectStatus.
    status: str = Field(max_length=30, index=True)

    # --- The enrolment funnel. Each step is a date so the drop-off between
    # --- them can be charted directly.
    screening_date: date | None = Field(default=None)
    enrollment_date: date | None = Field(default=None)  # consent + eligibility met
    randomization_date: date | None = Field(default=None)

    # One of enums.StudyArm. In a blinded trial the coordinator would not see
    # this; it is stored here so the demo can show group comparisons.
    arm: str = Field(max_length=30, index=True)

    # --- Demographics, coarse enough not to identify anyone.
    year_of_birth: int | None = Field(default=None)
    age_at_enrollment: int | None = Field(default=None)
    sex: str = Field(max_length=20)  # one of enums.Sex

    height_cm: float | None = Field(default=None)
    weight_kg: float | None = Field(default=None)

    # --- Ayurveda-specific baseline. One of enums.Prakriti; Phase 6 expands
    # --- this into a full per-dosha assessment.
    prakriti: str | None = Field(default=None, max_length=30, index=True)
    suppqual: dict = Field(default_factory=dict, sa_column=Column(JSONB))

    # --- Exits.
    completed_date: date | None = Field(default=None)
    withdrawal_date: date | None = Field(default=None)
    withdrawal_reason: str | None = Field(default=None, max_length=500)
    screen_failure_reason: str | None = Field(default=None, max_length=500)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
