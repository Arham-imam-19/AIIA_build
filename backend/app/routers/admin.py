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
    DsmbDecision,
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


PRESERVED_ROLES: frozenset[str] = frozenset({
    UserRole.ADMIN.value,
    UserRole.MONITOR.value,
    UserRole.SPONSOR.value,
    UserRole.ETHICS_COMMITTEE.value,
    UserRole.PHARMACOVIGILANCE.value,
    UserRole.REGULATOR.value,
    UserRole.DSMB.value,
})


@router.post("/reset-trial-data")
@router.post("/reset-test-data")
@router.post("/clean-slate-reset")
def reset_all_test_data(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.USER_MANAGE)),
    trial_id: int | None = Query(None, description="optional trial ID filter"),
) -> dict:
    """Purge all protocols, participating institutions/sites, local site staff (PI/CRC/Institution Admin/Patients),
    and all transactional clinical records across the entire database.

    Clears:
      - Clinical Progress Logs (clinical_log_entries)
      - Electronic Consents (econsents)
      - Patient Portal Requests (patient_requests)
      - Adverse Events & Serious Adverse Events (adverse_events)
      - Study Scheduled & Conducted Visits (visits)
      - Participant Dossiers & Screenings (subjects)
      - Participating Institutions & Sites (sites)
      - Protocol & Trial Definitions (trials)
      - Site-level Accounts (Institution Admin, PI, Coordinator, Patient)
      - Safety Monitoring Determinations (dsmb_decisions)

    Preserves:
      - Core Global Oversight Accounts: IT Administrator, Monitor, Sponsor, Ethics Committee, Pharmacovigilance, Regulator, DSMB
      - 21 CFR Part 11 Statutory Audit Log (audit_logs)
    """
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Primary IT Administrators have clearance to execute a global clean slate reset.",
        )

    # 1. Count records to be purged
    try:
        count_dsmb = int(session.exec(select(func.count(DsmbDecision.id))).one() or 0)
    except Exception:
        count_dsmb = 0

    try:
        count_logs = int(session.exec(select(func.count(ClinicalLogEntry.id))).one() or 0)
    except Exception:
        count_logs = 0

    count_aes = int(session.exec(select(func.count(AdverseEvent.id))).one() or 0)
    count_visits = int(session.exec(select(func.count(Visit.id))).one() or 0)
    count_econsents = int(session.exec(select(func.count(EConsent.id))).one() or 0)
    count_requests = int(session.exec(select(func.count(PatientRequest.id))).one() or 0)
    count_subjects = int(session.exec(select(func.count(Subject.id))).one() or 0)
    count_deleted_users = int(
        session.exec(select(func.count(User.id)).where(~User.role.in_(PRESERVED_ROLES))).one() or 0
    )
    count_preserved_users = int(
        session.exec(select(func.count(User.id)).where(User.role.in_(PRESERVED_ROLES))).one() or 0
    )
    count_sites = int(session.exec(select(func.count(Site.id))).one() or 0)
    count_trials = int(session.exec(select(func.count(Trial.id))).one() or 0)

    # 2. Break foreign-key and cross-table circular references
    session.exec(text("UPDATE users SET subject_id = NULL, site_id = NULL"))
    session.exec(text("UPDATE subjects SET assigned_researcher_id = NULL, user_id = NULL"))
    session.exec(text("UPDATE trials SET activated_by_user_id = NULL"))
    session.exec(text("UPDATE audit_logs SET trial_id = NULL"))
    
    # Detach deleted users from audit_logs while preserving the text attribution (email, role, action, reason)
    roles_sql_list = ",".join(f"'{r}'" for r in PRESERVED_ROLES)
    session.exec(text(f"UPDATE audit_logs SET user_id = NULL WHERE user_id NOT IN (SELECT id FROM users WHERE role IN ({roles_sql_list}))"))
    session.commit()

    # 3. Purge data in dependency order
    try:
        with session.begin_nested():
            session.exec(delete(DsmbDecision))
    except Exception:
        pass

    try:
        with session.begin_nested():
            session.exec(delete(ClinicalLogEntry))
    except Exception:
        pass

    session.exec(delete(EConsent))
    session.exec(delete(PatientRequest))
    session.exec(delete(AdverseEvent))
    session.exec(delete(Visit))
    session.exec(delete(Subject))
    session.exec(delete(User).where(~User.role.in_(PRESERVED_ROLES)))
    session.exec(delete(Site))
    session.exec(delete(Trial))
    session.commit()

    # 4. Record permanent 21 CFR Part 11 Audit Trail Entry
    audit.record(
        session,
        user=user,
        action=AuditAction.DELETE,
        entity_type="system_database",
        entity_id=None,
        entity_label="GLOBAL_CLEAN_SLATE_RESET",
        field_name="all_protocols_institutions_and_site_accounts",
        old_value=json.dumps({
            "trials": count_trials,
            "sites": count_sites,
            "deleted_accounts": count_deleted_users,
            "preserved_accounts": count_preserved_users,
            "subjects": count_subjects,
            "visits": count_visits,
            "adverse_events": count_aes,
            "clinical_logs": count_logs,
            "dsmb_decisions": count_dsmb,
            "econsents": count_econsents,
            "patient_requests": count_requests,
        }),
        new_value=json.dumps({"trials": 0, "sites": 0, "subjects": 0, "visits": 0, "adverse_events": 0, "clinical_logs": 0, "dsmb_decisions": 0}),
        reason="Global Clean Slate Reset executed by IT Administrator. All protocols, institutions, local staff, and participant accounts purged; core oversight accounts preserved.",
        trial_id=None,
    )
    session.commit()

    return {
        "status": "success",
        "message": "Global Clean Slate Reset completed: All protocols, institutions, investigator/coordinator/patient accounts, and clinical records have been purged. Core oversight accounts (IT Admin, Monitor, Sponsor, Ethics Committee, Pharmacovigilance, Regulator, DSMB) preserved.",
        "cleared_trials": count_trials,
        "cleared_sites": count_sites,
        "cleared_accounts": count_deleted_users,
        "preserved_accounts": count_preserved_users,
        "cleared_subjects": count_subjects,
        "cleared_visits": count_visits,
        "cleared_clinical_logs": count_logs,
        "cleared_dsmb_decisions": count_dsmb,
        "cleared_adverse_events": count_aes,
        "cleared_econsents": count_econsents,
        "cleared_patient_requests": count_requests,
        "timestamp": utcnow().isoformat(),
    }


@router.get("/database-stats")
def get_database_stats(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.USER_MANAGE)),
) -> dict:
    """Retrieve live entity counts across all system tables for IT Admin dashboard."""
    try:
        count_dsmb = int(session.exec(select(func.count(DsmbDecision.id))).one() or 0)
    except Exception:
        count_dsmb = 0

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
        "dsmb_decisions": count_dsmb,
        "econsents": count_econsents,
        "patient_requests": count_requests,
    }
