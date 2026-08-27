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
    """The user roles across the hierarchy, from Primary Admin to Patient.

    RBAC (role-based access control) means permissions hang off these roles
    rather than off individual people - like a hotel keycard that opens your
    floor, while the manager's opens all of them.
    """

    ADMIN = "admin"  # Primary / System Administrator (creates institutions, oversees system)
    INSTITUTION_ADMIN = "institution_admin"  # Institution / Site Administrator (manages site & researchers)
    PRINCIPAL_INVESTIGATOR = "principal_investigator"  # Lead Researcher at a site
    COORDINATOR = "coordinator"  # Clinical Research Coordinator (enters data, manages visits)
    SPONSOR = "sponsor"  # funds the trial, watches cost and timelines
    ETHICS_COMMITTEE = "ethics_committee"  # approves the trial, reviews safety
    REGULATOR = "regulator"  # CDSCO / Ministry of Ayush oversight
    PATIENT = "patient"  # Trial participant (can view schedule and contact Institution Admin)


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


class StudyArm(str, Enum):
    """The randomised groups in this protocol (1:1 allocation)."""

    TREATMENT = "treatment"  # Ashwagandha root churna
    PLACEBO = "placebo"  # matched placebo churna
    NOT_RANDOMIZED = "not_randomized"  # for screened/failed participants


class Sex(str, Enum):
    """Biological sex as captured for CDISC SDTM DM (Demographics) domain."""

    MALE = "M"
    FEMALE = "F"
    OTHER = "O"


class Prakriti(str, Enum):
    """Ayurvedic constitutional phenotype, assessed at baseline.

    This is the core domain differentiator: a modern clinical trial stratified
    by Ayurvedic constitution to test whether response to Ashwagandha varies by
    dosha predominance.
    """

    VATA = "vata"
    PITTA = "pitta"
    KAPHA = "kapha"
    VATA_PITTA = "vata_pitta"
    PITTA_KAPHA = "pitta_kapha"
    VATA_KAPHA = "vata_kapha"
    TRIDOSHIC = "tridoshic"


class VisitStatus(str, Enum):
    """State of an individual protocol visit."""

    SCHEDULED = "scheduled"  # in the calendar, date set
    COMPLETED = "completed"  # participant attended, data collected
    MISSED = "missed"  # window closed without a visit
    CANCELLED = "cancelled"  # e.g. after early withdrawal


class AESeverity(str, Enum):
    """CTCAE / ICH-GCP severity grading."""

    MILD = "mild"  # awareness of sign/symptom, easily tolerated
    MODERATE = "moderate"  # discomfort enough to interfere with usual activity
    SEVERE = "severe"  # incapacitating, unable to work or do daily activity


class AECausality(str, Enum):
    """Investigator's attribution of the event to the study drug.

    Follows the WHO-UMC causality categories used in Indian pharmacovigilance.
    """

    CERTAIN = "certain"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    CONDITIONAL = "conditional"
    UNCLASSIFIABLE = "unclassifiable"
    UNRELATED = "unrelated"
    NOT_ASSESSABLE = "not_assessable"


class AEOutcome(str, Enum):
    """Status of the event at the time of reporting."""

    RECOVERED = "recovered"
    RECOVERING = "recovering"
    ONGOING = "ongoing"
    NOT_RECOVERED = "not_recovered"
    RECOVERED_WITH_SEQUELAE = "recovered_with_sequelae"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class PatientRequestCategory(str, Enum):
    """Categories of participant inquiries submitted to Institution Admins."""

    SYMPTOM_INQUIRY = "symptom_inquiry"  # reporting or asking about a symptom / reaction
    APPOINTMENT_RESCHEDULE = "appointment_reschedule"  # request to change upcoming visit date
    ADVERSE_EVENT_ALERT = "adverse_event_alert"  # notifying hospital of an adverse occurrence
    MEDICATION_QUERY = "medication_query"  # posology / dosage / administration question
    GRIEVANCE = "grievance"  # complaint or compliance concern
    GENERAL_INQUIRY = "general_inquiry"  # trial logistics or general contact


class PatientRequestStatus(str, Enum):
    """Lifecycle status of a patient request."""

    SUBMITTED = "submitted"  # newly submitted by patient
    IN_REVIEW = "in_review"  # under review by institution admin / coordinator
    RESOLVED = "resolved"  # response sent and resolved
    ESCALATED = "escalated"  # escalated to PI or Ethics Committee


class ConsentStatus(str, Enum):
    """Lifecycle status of a participant's electronic informed consent."""

    PENDING = "pending"  # not yet signed
    SIGNED = "signed"  # digitally signed and verified
    REVOKED = "revoked"  # consent withdrawn by participant


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
    RESPOND = "respond"  # responding to a patient request or inquiry


def values(enum_cls: type[Enum]) -> list[str]:
    """All allowed strings for an enum, handy for validation and API docs."""
    return [member.value for member in enum_cls]
