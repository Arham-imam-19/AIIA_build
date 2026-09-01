"""Trial sites - the hospitals and institutes where the trial actually runs."""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class Site(SQLModel, table=True):
    """One participating hospital or institute.

    A multi-centre trial runs the same protocol at several sites at once, partly
    to recruit enough people and partly so the result is not an artefact of one
    hospital's population.

    Simplification for this project: a site row belongs to exactly one trial. In
    reality an institute runs many trials, which would be a many-to-many link.
    One-trial-per-row keeps every query in the dashboards a simple filter.
    """

    __tablename__ = "sites"

    id: int | None = Field(default=None, primary_key=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)

    # Short code used in subject identifiers, e.g. "01" -> AIIA-ASH-01-014.
    site_code: str = Field(max_length=20, index=True)
    name: str = Field(max_length=300)

    city: str = Field(max_length=120)
    state: str = Field(max_length=120)
    country: str = Field(default="India", max_length=120)

    # The Principal Investigator is the clinician answerable for the trial at
    # this site - the buck stops with them for protocol and patient safety.
    pi_name: str = Field(max_length=200)
    pi_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=40)

    # One of enums.SiteStatus.
    status: str = Field(max_length=30, index=True)

    # This site's share of the trial's overall recruitment goal.
    target_enrollment: int = Field(default=0)

    activation_date: date | None = Field(default=None)
    closed_date: date | None = Field(default=None)

    created_at: datetime = Field(default_factory=utcnow)
