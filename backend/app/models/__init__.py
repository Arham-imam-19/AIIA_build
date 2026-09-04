"""All database models, re-exported from one place.

Import from here rather than from the individual modules:

    from app.models import Trial, Subject, AdverseEvent

Alembic also imports this package so that `SQLModel.metadata` knows about every
table before it compares the models against the database.
"""

from app.models.adverse_event import AdverseEvent
from app.models.audit import AuditLog
from app.models.base import utcnow
from app.enums import (
    AECausality,
    AEOutcome,
    AESeverity,
    AuditAction,
    ConsentStatus,
    EthicsApprovalStatus,
    PatientRequestCategory,
    PatientRequestStatus,
    Prakriti,
    Sex,
    SiteStatus,
    StudyArm,
    SubjectStatus,
    TrialPhase,
    TrialStatus,
    UserRole,
    VisitStatus,
    values,
)
from app.models.clinical_log import ClinicalLogEntry
from app.models.dsmb import DsmbDecision
from app.models.econsent import EConsent
from app.models.patient_request import PatientRequest
from app.models.site import Site
from app.models.subject import Subject
from app.models.trial import Trial
from app.models.user import User
from app.models.visit import Visit

__all__ = [
    # Tables, in dependency order (trials first, audit last).
    "Trial",
    "Site",
    "User",
    "Subject",
    "ClinicalLogEntry",
    "DsmbDecision",
    "Visit",
    "AdverseEvent",
    "PatientRequest",
    "EConsent",
    "AuditLog",
    # Vocabularies.
    "UserRole",
    "TrialStatus",
    "TrialPhase",
    "SiteStatus",
    "SubjectStatus",
    "StudyArm",
    "Sex",
    "Prakriti",
    "VisitStatus",
    "AESeverity",
    "AECausality",
    "AEOutcome",
    "PatientRequestCategory",
    "PatientRequestStatus",
    "ConsentStatus",
    "AuditAction",
    "EthicsApprovalStatus",
    # Helpers.
    "values",
    "utcnow",
]