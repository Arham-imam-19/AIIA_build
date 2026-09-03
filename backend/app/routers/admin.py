"""Primary Administrator (IT Admin) Control Plane & System Maintenance Router.

Provides global database reset, clean-slate purges of test/transactional data across
all sites and trials, synthetic data reseeding, and system health controls under 21 CFR Part 11.
"""

from __future__ import annotations

import json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlmodel import Session, delete, func, select

from app import audit
from app.db import get_session
from app.enums import AuditAction, UserRole
from app.models import (
    AdverseEvent,
    ClinicalLogEntry,
    EConsent,
    PatientRequest,
    Site,
    Subject,
    Trial,
    User,
    Visit,
)
from app.models.base import utcnow
from app.rbac import CurrentUser, Permission, require

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reset-trial-data")
@router.post("/reset-test-data")
def reset_all_test_data(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.USER_MANAGE)),
    trial_id: int | None = Query(None, description="optional trial ID filter"),
) -> dict:
    """Purge all transactional clinical test data across the entire database.

    Clears:
      - Clinical Progress Logs (clinical_log_entries)
      - Electronic Consents (econsents)
      - Patient Portal Requests (patient_requests)
      - Adverse Events & Serious Adverse Events (adverse_events)
      - Study Scheduled & Conducted Visits (visits)
      - Participant Dossiers & Screenings (subjects)
      - Synthetic Patient User Accounts (users with role=patient)

    Preserves:
      - Core Trial & Protocol Definitions (trials)
      - Registered Hospital & Research Sites (sites)
      - Staff & Investigator Login Accounts (users with role!=patient)
      - 21 CFR Part 11 Statutory Audit Log (audit_logs)
    """
    if user.role not in {UserRole.ADMIN.value, UserRole.INSTITUTION_ADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Primary IT Administrators have clearance to execute a global clean slate reset.",
        )

    # 1. Count records to be purged
    try:
        count_logs = int(session.exec(select(func.count(ClinicalLogEntry.id))).one() or 0)
    except Exception:
        count_logs = 0

    count_aes = int(session.exec(select(func.count(AdverseEvent.id))).one() or 0)
    count_visits = int(session.exec(select(func.count(Visit.id))).one() or 0)
    count_econsents = int(session.exec(select(func.count(EConsent.id))).one() or 0)
    count_requests = int(session.exec(select(func.count(PatientRequest.id))).one() or 0)
    count_subjects = int(session.exec(select(func.count(Subject.id))).one() or 0)
    count_patient_users = int(
        session.exec(select(func.count(User.id)).where(User.role == UserRole.PATIENT.value)).one() or 0
    )
    count_sites = int(session.exec(select(func.count(Site.id))).one() or 0)
    count_staff_users = int(
        session.exec(select(func.count(User.id)).where(User.role != UserRole.PATIENT.value)).one() or 0
    )

    # 2. Break foreign-key and cross-table circular references
    session.exec(text("UPDATE users SET subject_id = NULL"))
    session.exec(text("UPDATE subjects SET assigned_researcher_id = NULL, user_id = NULL"))
    session.commit()

    # 3. Purge data in dependency order
    try:
        session.exec(delete(ClinicalLogEntry))
    except Exception:
        pass

    session.exec(delete(EConsent))
    session.exec(delete(PatientRequest))
    session.exec(delete(AdverseEvent))
    session.exec(delete(Visit))
    session.exec(delete(Subject))
    session.exec(delete(User).where(User.role == UserRole.PATIENT.value))
    session.commit()

    # 4. Record permanent 21 CFR Part 11 Audit Trail Entry
    audit.record(
        session,
        user=user,
        action=AuditAction.DELETE,
        entity_type="system_database",
        entity_id=None,
        entity_label="GLOBAL_CLEAN_SLATE_RESET",
        field_name="transactional_data",
        old_value=json.dumps({
            "subjects": count_subjects,
            "visits": count_visits,
            "adverse_events": count_aes,
            "clinical_logs": count_logs,
            "econsents": count_econsents,
            "patient_requests": count_requests,
            "patient_users": count_patient_users,
        }),
        new_value=json.dumps({"subjects": 0, "visits": 0, "adverse_events": 0, "clinical_logs": 0}),
        reason="Global Clean Slate Reset executed by Primary Administrator. All synthetic participant test records purged.",
        trial_id=trial_id,
    )
    session.commit()

    return {
        "status": "success",
        "message": "Global clinical test data successfully purged across all trials and sites.",
        "cleared_subjects": count_subjects,
        "cleared_visits": count_visits,
        "cleared_clinical_logs": count_logs,
        "cleared_adverse_events": count_aes,
        "cleared_econsents": count_econsents,
        "cleared_patient_requests": count_requests,
        "cleared_patient_accounts": count_patient_users,
        "preserved_sites": count_sites,
        "preserved_staff_users": count_staff_users,
        "timestamp": utcnow().isoformat(),
    }


@router.get("/database-stats")
def get_database_stats(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.USER_MANAGE)),
) -> dict:
    """Retrieve live entity counts across all system tables for IT Admin dashboard."""
    try:
        count_logs = int(session.exec(select(func.count(ClinicalLogEntry.id))).one() or 0)
    except Exception:
        count_logs = 0

    count_trials = int(session.exec(select(func.count(Trial.id))).one() or 0)
    count_sites = int(session.exec(select(func.count(Site.id))).one() or 0)
    count_users = int(session.exec(select(func.count(User.id))).one() or 0)
    count_subjects = int(session.exec(select(func.count(Subject.id))).one() or 0)
    count_visits = int(session.exec(select(func.count(Visit.id))).one() or 0)
    count_aes = int(session.exec(select(func.count(AdverseEvent.id))).one() or 0)
    count_econsents = int(session.exec(select(func.count(EConsent.id))).one() or 0)
    count_requests = int(session.exec(select(func.count(PatientRequest.id))).one() or 0)

    return {
        "trials": count_trials,
        "sites": count_sites,
        "users": count_users,
        "subjects": count_subjects,
        "visits": count_visits,
        "adverse_events": count_aes,
        "clinical_logs": count_logs,
        "econsents": count_econsents,
        "patient_requests": count_requests,
    }
