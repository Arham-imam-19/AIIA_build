"""Study visits - the protocol's timetable of appointments."""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class Visit(SQLModel, table=True):
    """One appointment for one participant.

    The protocol fixes a schedule - screening, baseline, then follow-ups at set
    intervals - and each participant gets a row per scheduled visit. Comparing
    `scheduled_date` with `actual_date` is how a trial spots slippage.

    A **protocol deviation** is anything that departed from the protocol: a visit
    outside its allowed window, a missed assessment, a dose given late. They are
    normal and expected; what matters to a regulator is that every one is
    recorded rather than quietly fixed. That is why the flag lives here rather
    than being inferred later.
    """

    __tablename__ = "visits"

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)

    # Human name from the protocol, e.g. "Week 4 Follow-up".
    visit_name: str = Field(max_length=120)
    # Position in the schedule, 1-based, so visits sort correctly.
    visit_number: int = Field(index=True)
    # Protocol day relative to baseline: -14 for screening, 0 for baseline,
    # 28 for the week-4 visit, and so on.
    visit_day: int

    scheduled_date: date | None = Field(default=None)
    actual_date: date | None = Field(default=None)

    # One of enums.VisitStatus.
    status: str = Field(max_length=30, index=True)

    is_protocol_deviation: bool = Field(default=False, index=True)
    deviation_description: str | None = Field(default=None, max_length=1000)

    notes: str | None = Field(default=None, max_length=2000)

    # Which coordinator or investigator recorded the visit.
    performed_by_user_id: int | None = Field(
        default=None, foreign_key="users.id", index=True
    )

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
