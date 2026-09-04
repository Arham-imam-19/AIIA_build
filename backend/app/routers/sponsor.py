"""Sponsor portfolio oversight endpoints.

Strictly read-only portfolio-wide oversight APIs providing live aggregations
for patient enrollment trajectories, safety distributions, regulatory/ethics
milestones, statutory 24-hour SAE reporting clocks, and institute drill-downs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from app.db import get_session
from app.models import AdverseEvent, Site, Subject, Trial, Visit
from app.models.base import utcnow
from app.rbac import CurrentUser, Permission, require
from app.routers.stats import resolve_trial

router = APIRouter(prefix="/api/sponsor", tags=["sponsor"])


def _assert_portfolio_access(user: CurrentUser) -> None:
    """Enforce server-side role check for portfolio-wide management oversight.

    Site-scoped staff (e.g. Coordinators or PIs) attempting to access portfolio-wide
    sponsor endpoints are denied with HTTP 403.
    """
    if user.is_site_scoped:
        raise HTTPException(
            status_code=403,
            detail=(
                "Portfolio-wide sponsor oversight data is restricted to management "
                f"oversight roles. Your current account ({user.role_label}) is scoped to Site {user.site_id}."
            ),
        )


@router.get("/analytics")
def get_sponsor_analytics(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    trial_id: int | None = Query(None, description="restrict to one trial"),
) -> dict:
    """Live database aggregate queries for recruitment trajectory and safety distributions."""
    _assert_portfolio_access(user)

    trial = resolve_trial(session, trial_id)
    if trial is None:
        return {"enrollment_curve": [], "safety_distribution": [], "deltas": {}}

    tid = trial.id
    today = date.today()
    target = trial.target_enrollment or 100

    # 1. Real Patient Enrollment Curve (Monthly aggregate from actual subjects table)
    sub_dates = session.exec(
        select(Subject.enrollment_date)
        .where(Subject.trial_id == tid, Subject.enrollment_date.is_not(None))
        .order_by(Subject.enrollment_date)
    ).all()

    month_counts: dict[str, int] = {}
    for d in sub_dates:
        key = d.strftime("%b %Y")
        month_counts[key] = month_counts.get(key, 0) + 1

    cumulative = 0
    enrollment_curve = []
    for month, count in month_counts.items():
        cumulative += count
        enrollment_curve.append({
            "name": month,
            "New": count,
            "Total": cumulative,
            "Target": target,
        })

    # If no subjects have enrolled yet, provide an initial baseline point
    if not enrollment_curve:
        curr_month = today.strftime("%b %Y")
        enrollment_curve.append({
            "name": curr_month,
            "New": 0,
            "Total": 0,
            "Target": target,
        })

    # 2. Real AE Distribution Across Participating Sites
    sites = session.exec(
        select(Site).where(Site.trial_id == tid).order_by(Site.site_code)
    ).all()

    aes = session.exec(
        select(AdverseEvent).where(AdverseEvent.trial_id == tid)
    ).all()

    site_map: dict[int, dict] = {
        s.id: {
            "site_id": s.id,
            "site_code": s.site_code,
            "name": s.name,
            "city": s.city,
            "Mild": 0,
            "Moderate": 0,
            "Severe": 0,
            "SAE": 0,
            "Total": 0,
        }
        for s in sites
    }

    for ae in aes:
        s_data = site_map.get(ae.site_id)
        if s_data:
            s_data["Total"] += 1
            if ae.is_serious:
                s_data["SAE"] += 1
            elif ae.severity == "severe":
                s_data["Severe"] += 1
            elif ae.severity == "moderate":
                s_data["Moderate"] += 1
            else:
                s_data["Mild"] += 1

    safety_distribution = list(site_map.values())

    # 3. Week-over-week deltas for Stat Cards
    week_ago = today - timedelta(days=7)
    enrolled_this_week = session.exec(
        select(func.count(Subject.id)).where(
            Subject.trial_id == tid,
            Subject.enrollment_date >= week_ago,
        )
    ).one()

    screened_this_week = session.exec(
        select(func.count(Subject.id)).where(
            Subject.trial_id == tid,
            Subject.screening_date >= week_ago,
        )
    ).one()

    aes_this_week = session.exec(
        select(func.count(AdverseEvent.id)).where(
            AdverseEvent.trial_id == tid,
            AdverseEvent.onset_date >= week_ago,
        )
    ).one()

    # 4. DPDP Act 2023 Consent Compliance Percentage
    total_enrolled = session.exec(
        select(func.count(Subject.id)).where(
            Subject.trial_id == tid,
            Subject.status.in_(["enrolled", "active", "completed"]),
        )
    ).one()

    unwithdrawn_consent = session.exec(
        select(func.count(Subject.id)).where(
            Subject.trial_id == tid,
            Subject.status.in_(["enrolled", "active", "completed"]),
            Subject.withdrawal_of_consent == False,
        )
    ).one()

    consent_compliance_pct = (
        round((unwithdrawn_consent / total_enrolled * 100), 1)
        if total_enrolled > 0
        else 100.0
    )

    return {
        "trial_id": tid,
        "protocol_number": trial.protocol_number,
        "enrollment_curve": enrollment_curve,
        "safety_distribution": safety_distribution,
        "deltas": {
            "enrolled_this_week": enrolled_this_week,
            "screened_this_week": screened_this_week,
            "aes_this_week": aes_this_week,
        },
        "consent_compliance_pct": consent_compliance_pct,
    }


@router.get("/regulatory-milestones")
def get_regulatory_milestones(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    trial_id: int | None = Query(None, description="restrict to one trial"),
) -> list[dict]:
    """Milestone compliance tracker: CTRI registration, IEC approval, and annual renewal deadlines."""
    _assert_portfolio_access(user)

    today = date.today()
    statement = select(Trial)
    if trial_id:
        statement = statement.where(Trial.id == trial_id)

    trials = session.exec(statement.order_by(Trial.id)).all()
    records = []

    for t in trials:
        is_recruiting = t.status == "recruiting"
        has_ctri = bool(t.ctri_number and t.ctri_number.strip())

        if has_ctri:
            ctri_status = "REGISTERED"
            ctri_tone = "good"
        elif is_recruiting:
            ctri_status = "OVERDUE_ALERT (Recruiting without CTRI)"
            ctri_tone = "bad"
        else:
            ctri_status = "PENDING_REGISTRATION"
            ctri_tone = "warn"

        ec_status = (t.ethics_approval_status or "pending").upper()
        ec_tone = "good" if ec_status == "APPROVED" else "bad"

        # Ethics Committee renewal deadline logic
        renewal_status = "COMPLIANT"
        renewal_tone = "good"
        days_left = None

        if t.ethics_approval_valid_until:
            days_left = (t.ethics_approval_valid_until - today).days
            if days_left < 0:
                renewal_status = f"OVERDUE ({abs(days_left)} days past expiry)"
                renewal_tone = "bad"
            elif days_left <= 30:
                renewal_status = f"DUE SOON ({days_left} days remaining)"
                renewal_tone = "warn"
            else:
                renewal_status = f"VALID ({days_left} days remaining)"
                renewal_tone = "good"
        else:
            renewal_status = "NO EXPIRY DOCUMENTED"
            renewal_tone = "warn"

        records.append({
            "trial_id": t.id,
            "protocol_number": t.protocol_number,
            "title": t.short_title or t.title,
            "phase": t.phase,
            "status": t.status,
            "ctri_number": t.ctri_number or "Not Registered",
            "ctri_date": str(t.ctri_registration_date) if t.ctri_registration_date else None,
            "ctri_status": ctri_status,
            "ctri_tone": ctri_tone,
            "ec_number": t.ethics_approval_number or "Pending Review",
            "ec_status": ec_status,
            "ec_tone": ec_tone,
            "ec_approval_date": str(t.ethics_approval_date) if t.ethics_approval_date else None,
            "ec_valid_until": str(t.ethics_approval_valid_until) if t.ethics_approval_valid_until else "Not Documented",
            "renewal_status": renewal_status,
            "renewal_tone": renewal_tone,
            "days_to_renewal": days_left,
            "regulatory_number": t.regulatory_approval_number or "CDSCO / AYUSH Standard Clearance",
            "regulatory_date": str(t.regulatory_approval_date) if t.regulatory_approval_date else None,
        })

    return records


@router.get("/sae-queue")
def get_sae_queue(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.AE_READ)),
    trial_id: int | None = Query(None, description="restrict to one trial"),
) -> list[dict]:
    """Open SAE queue with live 24-hour statutory regulatory reporting clocks (NDCT Rules 2019 Rule 42)."""
    _assert_portfolio_access(user)

    now = datetime.now(timezone.utc)
    statement = (
        select(AdverseEvent, Subject.subject_code, Site.site_code, Site.name)
        .join(Subject, AdverseEvent.subject_id == Subject.id)
        .join(Site, AdverseEvent.site_id == Site.id)
        .where(AdverseEvent.is_serious == True)
    )
    if trial_id:
        statement = statement.where(AdverseEvent.trial_id == trial_id)

    results = session.exec(statement.order_by(AdverseEvent.created_at.desc())).all()
    queue = []

    for ae, sub_code, site_code, site_name in results:
        # Created timestamp with tzinfo for accurate clock subtraction
        created_at_utc = (
            ae.created_at.replace(tzinfo=timezone.utc)
            if ae.created_at.tzinfo is None
            else ae.created_at
        )
        elapsed_hours = (now - created_at_utc).total_seconds() / 3600.0
        hours_remaining = max(0.0, 24.0 - elapsed_hours)

        is_reported = bool(ae.reported_to_ec or ae.ec_decision)
        if ae.ec_decision:
            clock_status = "REPORTED_TO_EC"
            clock_label = f"Adjudicated ({ae.ec_decision.upper()})"
            tone = "good"
        elif ae.reported_to_ec:
            clock_status = "REPORTED_TO_EC"
            clock_label = f"Reported ({ae.reported_to_ec_date})"
            tone = "good"
        elif elapsed_hours > 24.0:
            clock_status = "OVERDUE"
            clock_label = f"OVERDUE ({round(elapsed_hours - 24.0, 1)}h past 24h deadline)"
            tone = "bad"
        elif elapsed_hours >= 18.0:
            clock_status = "DUE_SOON"
            clock_label = f"DUE SOON ({round(hours_remaining, 1)}h remaining)"
            tone = "warn"
        else:
            clock_status = "WITHIN_WINDOW"
            clock_label = f"Within Window ({round(hours_remaining, 1)}h remaining)"
            tone = "neutral"

        queue.append({
            "id": ae.id,
            "ae_number": ae.ae_number,
            "subject_code": sub_code,
            "site_code": site_code,
            "site_name": site_name,
            "term_verbatim": ae.term_verbatim,
            "severity": ae.severity,
            "seriousness_criteria": ae.seriousness_criteria or "Medically Significant",
            "causality": ae.causality,
            "outcome": ae.outcome,
            "onset_date": str(ae.onset_date),
            "created_at": created_at_utc.isoformat(),
            "reported_to_ec": is_reported,
            "reported_to_ec_date": str(ae.reported_to_ec_date or ae.ec_decision_date) if (ae.reported_to_ec_date or ae.ec_decision_date) else None,
            "ec_decision": ae.ec_decision,
            "ec_decision_date": str(ae.ec_decision_date) if ae.ec_decision_date else None,
            "clock_status": clock_status,
            "clock_label": clock_label,
            "tone": tone,
            "hours_remaining": round(hours_remaining, 1),
            "elapsed_hours": round(elapsed_hours, 1),
        })

    return queue


@router.get("/institutes/{site_id}/drilldown")
def get_institute_drilldown(
    site_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
) -> dict:
    """Detailed tabular breakdown of protocols, recruitment, safety, and deviations for one institute."""
    _assert_portfolio_access(user)

    site = session.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site with ID {site_id} not found")

    trial = session.get(Trial, site.trial_id)

    # Scoped aggregates for this specific institute
    screened_count = session.exec(
        select(func.count(Subject.id)).where(Subject.site_id == site.id)
    ).one()

    enrolled_count = session.exec(
        select(func.count(Subject.id)).where(
            Subject.site_id == site.id,
            (
                Subject.status.in_(["enrolled", "active", "completed"])
                | Subject.enrollment_date.is_not(None)
            ),
        )
    ).one()

    target = site.target_enrollment or 1
    pct_target = round((enrolled_count / target * 100), 1)

    open_ae_count = session.exec(
        select(func.count(AdverseEvent.id)).where(
            AdverseEvent.site_id == site.id,
            AdverseEvent.outcome != "recovered",
        )
    ).one()

    deviation_count = session.exec(
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            Subject.site_id == site.id,
            Visit.is_protocol_deviation == True,
        )
    ).one()

    completed_visits = session.exec(
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            Subject.site_id == site.id,
            Visit.status == "completed",
        )
    ).one()

    missed_visits = session.exec(
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            Subject.site_id == site.id,
            Visit.status == "missed",
        )
    ).one()

    visits_due = completed_visits + missed_visits
    deviation_rate = (
        round((deviation_count / visits_due * 100), 1) if visits_due > 0 else 0.0
    )

    screening_success_rate = (
        round((enrolled_count / screened_count * 100), 1) if screened_count > 0 else 0.0
    )

    # Outlier risk assessment
    is_high_deviation = deviation_rate > 15.0
    is_low_recruitment = pct_target < 50.0 and site.status == "recruiting"

    # Tabular study/department rows running at this institute
    studies = [
        {
            "study_id": trial.id if trial else site.trial_id,
            "department_study_name": f"{trial.protocol_number if trial else 'AIIA-PROTOCOL'} - {trial.short_title if trial else 'Clinical Study'}",
            "protocol_number": trial.protocol_number if trial else "AIIA-01",
            "pi_name": site.pi_name or "Dr. Principal Investigator",
            "screened": screened_count,
            "enrolled": enrolled_count,
            "target": target,
            "percent_of_target": pct_target,
            "status": site.status,
            "open_aes": open_ae_count,
            "deviations": deviation_count,
            "deviation_rate": deviation_rate,
            "screening_success_rate": screening_success_rate,
            "is_high_risk": is_high_deviation or is_low_recruitment,
            "risk_flags": [
                f"Elevated deviation rate ({deviation_rate}%)" if is_high_deviation else None,
                f"Recruitment lagging ({pct_target}% of target)" if is_low_recruitment else None,
            ],
        }
    ]

    return {
        "site_id": site.id,
        "site_code": site.site_code,
        "name": site.name,
        "city": site.city,
        "state": site.state,
        "status": site.status,
        "activation_date": str(site.activation_date) if site.activation_date else None,
        "studies": studies,
    }
