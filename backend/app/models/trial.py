"""The trial itself - the top-level record everything else hangs off."""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class Trial(SQLModel, table=True):
    """One clinical study.

    A trial is the protocol plus everything done under it. The protocol is the
    study's rulebook: who can join, what they receive, what gets measured and
    when. Every subject, visit and adverse event in the system belongs to one
    trial.
    """

    __tablename__ = "trials"

    id: int | None = Field(default=None, primary_key=True)

    # The sponsor's own identifier for the study, e.g. "AIIA-ASH-2026-01".
    protocol_number: str = Field(max_length=80, unique=True, index=True)

    title: str = Field(max_length=500)
    short_title: str = Field(max_length=200)

    # CTRI = Clinical Trials Registry - India. Indian trials must be registered
    # publicly there before the first participant is enrolled, the way a company
    # must be filed with the registrar before it trades. Null until registered.
    ctri_number: str | None = Field(
        default=None, max_length=80, unique=True, index=True
    )
    ctri_registration_date: date | None = Field(default=None)

    # One of enums.TrialPhase / enums.TrialStatus.
    phase: str = Field(max_length=20)
    status: str = Field(max_length=30, index=True)

    # What is being treated, in both biomedical and Ayurvedic terms. Recording
    # both is what makes the dataset usable by Ayush researchers and by
    # regulators reading it as a conventional trial.
    indication: str = Field(max_length=300)
    indication_ayurveda: str | None = Field(default=None, max_length=300)

    # The study medicine and what it is compared against.
    intervention: str = Field(max_length=500)
    comparator: str | None = Field(default=None, max_length=300)

    design: str = Field(max_length=300)
    is_blinded: bool = Field(default=True)

    primary_objective: str | None = Field(default=None, max_length=1000)
    secondary_objective: str | None = Field(default=None, max_length=1000)
    primary_endpoint: str | None = Field(default=None, max_length=500)

    sponsor_name: str = Field(max_length=200)
    sponsor_type: str | None = Field(default=None, max_length=80)

    # How many participants the study is designed to recruit. Actual enrolment
    # is deliberately NOT stored here - it is counted from the subjects table so
    # the two can never drift apart.
    target_enrollment: int = Field(default=0)

    start_date: date | None = Field(default=None)
    planned_end_date: date | None = Field(default=None)
    actual_end_date: date | None = Field(default=None)

    # Ethics approval: an independent committee must agree the study is
    # acceptable before it may run.
    ethics_approval_number: str | None = Field(default=None, max_length=120)
    ethics_approval_date: date | None = Field(default=None)

    # Regulatory approval under India's New Drugs and Clinical Trials Rules 2019
    # (the legal gates a trial passes through, in order). Phase 5 turns these
    # into enforced workflow gates and a compliance score.
    regulatory_approval_number: str | None = Field(default=None, max_length=120)
    regulatory_approval_date: date | None = Field(default=None)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
