"""Adverse events - the safety half of the system.

An **adverse event (AE)** is anything medically unwelcome that happens to a
participant during a trial, whether or not the treatment caused it. If someone
breaks an ankle cycling, that is still an AE. Deciding what the treatment is to
blame for is a separate judgement, recorded in `causality`.

**Pharmacovigilance** is the discipline of watching these events for patterns -
drug-safety monitoring. Phase 4 adds the NLP that reads `description` and the
signal detection that raises alerts.
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class AdverseEvent(SQLModel, table=True):
    """One reported adverse event."""

    __tablename__ = "adverse_events"

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)
    site_id: int = Field(foreign_key="sites.id", index=True)

    # Sequential number within the trial, e.g. AE-0042, for referring to it in
    # correspondence with the ethics committee.
    ae_number: str = Field(max_length=40, index=True)

    # The coordinator's short label for the event, as typed.
    term_verbatim: str = Field(max_length=300)

    # ---------------------------------------------------------------------
    # THE FREE-TEXT NARRATIVE. This is the raw input for the Phase 4 NLP.
    #
    # In real trials this field is messy: abbreviations (c/o = complains of,
    # IP = investigational product, x3 days = for three days), inconsistent
    # capitalisation, clinical shorthand. The seed data reproduces that mess on
    # purpose - an NLP engine that only works on clean prose would not survive
    # contact with a real trial.
    # ---------------------------------------------------------------------
    description: str = Field(max_length=4000)

    onset_date: date
    resolution_date: date | None = Field(default=None)

    # One of enums.AESeverity - how intense.
    severity: str = Field(max_length=20, index=True)

    # Seriousness is a SEPARATE regulatory concept from severity: an event is
    # "serious" (an SAE) if it caused death, was life-threatening, required
    # hospitalisation, caused lasting disability or a birth defect. A severe
    # headache is not serious; a moderate allergic reaction that puts someone in
    # hospital is. SAEs carry hard reporting deadlines.
    is_serious: bool = Field(default=False, index=True)
    seriousness_criteria: str | None = Field(default=None, max_length=300)

    # One of enums.AECausality - the investigator's blame assessment.
    causality: str = Field(max_length=30, index=True)
    # One of enums.AEOutcome - how it ended.
    outcome: str = Field(max_length=40, index=True)

    action_taken: str | None = Field(default=None, max_length=300)

    related_visit_id: int | None = Field(
        default=None, foreign_key="visits.id", index=True
    )

    # ---------------------------------------------------------------------
    # MedDRA coding. MedDRA is the standard dictionary regulators use so that
    # "loose motions", "diarrhoea" and "the runs" all become one code - like
    # mapping free-text job titles onto a fixed list so they can be counted.
    #   PT  = Preferred Term, the specific concept ("Diarrhoea")
    #   SOC = System Organ Class, the broad body-system bucket
    #         ("Gastrointestinal disorders")
    #
    # Left null by the Phase 1 seed. Phase 4 fills these in from `description`
    # and records how confident the model was.
    # ---------------------------------------------------------------------
    meddra_pt_code: str | None = Field(default=None, max_length=40, index=True)
    meddra_pt_term: str | None = Field(default=None, max_length=200)
    meddra_soc: str | None = Field(default=None, max_length=200, index=True)
    coding_confidence: float | None = Field(default=None)
    coding_reviewed_by_user_id: int | None = Field(
        default=None, foreign_key="users.id"
    )

    reported_by_user_id: int | None = Field(
        default=None, foreign_key="users.id", index=True
    )
    reported_date: date | None = Field(default=None)

    # Serious events must reach the ethics committee within a fixed window.
    # Phase 5 turns this into a compliance check with a deadline.
    reported_to_ec: bool = Field(default=False)
    reported_to_ec_date: date | None = Field(default=None)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
