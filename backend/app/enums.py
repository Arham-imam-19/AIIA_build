"""Controlled vocabularies for the whole system.

Why these are stored as plain strings in the database
----------------------------------------------------
Every enum below subclasses `str`, and the model columns are declared as `str`
(VARCHAR), not as SQL ENUM types. That is deliberate:

  * PostgreSQL native ENUMs need an `ALTER TYPE` migration every time a new
    value is added, which is painful when the vocabulary is still moving.
  * SQLAlchemy's Enum type persists the member *name* ("SEVERE"), while our API
    and seed data speak the *value* ("severe"). Storing strings removes that
    whole class of mismatch.

So these classes are the single source of truth for allowed values, used by the
seed script and by the API request schemas, while the database stores the plain
lowercase string.

In clinical-trial terms these vocabularies are not arbitrary: severity,
causality and outcome all follow the categories regulators expect on an
adverse-event report.
"""

from enum import Enum


class UserRole(str, Enum):
    """The five personas the dashboards are built for, plus an admin.

    RBAC (role-based access control) means permissions hang off these roles
    rather than off individual people - like a hotel keycard that opens your
    floor, while the manager's opens all of them.
    """

    PRINCIPAL_INVESTIGATOR = "principal_investigator"  # runs the trial at a site
    SPONSOR = "sponsor"  # funds the trial, watches cost and timelines
    ETHICS_COMMITTEE = "ethics_committee"  # approves the trial, reviews safety
    REGULATOR = "regulator"  # CDSCO / Ministry of Ayush oversight
    COORDINATOR = "coordinator"  # Clinical Research Coordinator, enters the data
    ADMIN = "admin"  # system administrator


class TrialStatus(str, Enum):
    """Where a trial sits in its lifecycle."""

    PLANNING = "planning"
    PENDING_ETHICS = "pending_ethics"  # submitted, awaiting ethics approval
    APPROVED = "approved"  # approved but not yet recruiting
    RECRUITING = "recruiting"
    ACTIVE = "active"  # fully enrolled, follow-up ongoing
    COMPLETED = "completed"
    SUSPENDED = "suspended"  # paused, e.g. after a safety signal
    TERMINATED = "terminated"  # stopped early for good


class TrialPhase(str, Enum):
    """How far along the evidence ladder a study is.

    Phase I asks "is it safe?", II "does it seem to work?", III "does it work
    better than the alternative, in a large group?", IV "what shows up once it
    is in real-world use?".
    """

    PILOT = "pilot"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"


class SiteStatus(str, Enum):
    """A site is one hospital or clinic taking part in the trial."""

    PLANNED = "planned"
    ACTIVATED = "activated"  # cleared to start, not yet enrolling
    RECRUITING = "recruiting"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class SubjectStatus(str, Enum):
    """A participant's journey through the trial.

    SCREENING -> (SCREEN_FAILED | ENROLLED -> ACTIVE -> COMPLETED)
    with WITHDRAWN / LOST_TO_FOLLOW_UP as exits at any point after enrolment.
    """

    SCREENING = "screening"
    SCREEN_FAILED = "screen_failed"  # did not meet eligibility criteria
    ENROLLED = "enrolled"  # consented and randomised, not yet dosed
    ACTIVE = "active"  # on treatment / in follow-up
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"  # left the trial, reason recorded
    LOST_TO_FOLLOW_UP = "lost_to_follow_up"  # stopped responding


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class StudyArm(str, Enum):
    """Which group a participant was randomised into.

    Randomisation = deciding by chance, so the two groups are comparable and the
    result cannot be explained by who was put where.
    """

    TREATMENT = "treatment"
    PLACEBO = "placebo"  # a look-alike with no active ingredient
    COMPARATOR = "comparator"  # an existing standard treatment
    NOT_RANDOMIZED = "not_randomized"


class Prakriti(str, Enum):
    """Ayurvedic constitutional type, recorded at baseline.

    A person's prakriti is their inborn body-mind constitution, expressed as the
    balance of three doshas (vata, pitta, kapha) - roughly a baseline body-type
    classification. Most people are a blend of two.

    Phase 6 expands this into a full prakriti assessment with per-dosha scores;
    this single field is the placeholder the seed data already populates.
    """

    VATA = "vata"
    PITTA = "pitta"
    KAPHA = "kapha"
    VATA_PITTA = "vata_pitta"
    PITTA_KAPHA = "pitta_kapha"
    VATA_KAPHA = "vata_kapha"
    TRIDOSHA = "tridosha"  # all three roughly balanced


class VisitStatus(str, Enum):
    """A visit is one scheduled appointment in the protocol's timetable."""

    SCHEDULED = "scheduled"  # in the future
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"  # window passed without the visit happening
    CANCELLED = "cancelled"


class AESeverity(str, Enum):
    """How intense an adverse event was.

    Note: severity is NOT the same as seriousness. A migraine can be *severe*
    (very painful) without being *serious* (life-threatening or requiring
    hospitalisation). Regulators care about both, separately.
    """

    MILD = "mild"  # noticeable, no interference with daily activity
    MODERATE = "moderate"  # interferes with daily activity
    SEVERE = "severe"  # prevents daily activity


class AECausality(str, Enum):
    """The investigator's judgement of whether the study treatment caused it."""

    UNRELATED = "unrelated"
    UNLIKELY = "unlikely"
    POSSIBLE = "possible"
    PROBABLE = "probable"
    DEFINITE = "definite"
    NOT_ASSESSABLE = "not_assessable"


class AEOutcome(str, Enum):
    """How the adverse event ended."""

    RECOVERED = "recovered"
    RECOVERING = "recovering"
    ONGOING = "ongoing"
    RECOVERED_WITH_SEQUELAE = "recovered_with_sequelae"  # better, but lasting effects
    FATAL = "fatal"
    UNKNOWN = "unknown"


class AuditAction(str, Enum):
    """What kind of thing happened, for the audit trail.

    An audit trail is the tamper-evident logbook regulators require (21 CFR
    Part 11): who did what, to which record, when, and why. Like a bank
    statement - you never erase a line, you only append a correction.
    """

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    SIGN = "sign"  # electronic signature applied
    APPROVE = "approve"
    REJECT = "reject"


def values(enum_cls: type[Enum]) -> list[str]:
    """All allowed strings for an enum, handy for validation and API docs."""
    return [member.value for member in enum_cls]
