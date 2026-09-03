"""One endpoint per screen: the dashboard, and the permission table behind it.

`GET /api/dashboard` returns whatever the logged-in user's role should see. There
is no `?role=` parameter, on purpose - the role comes from the token, so a
regulator cannot ask for the sponsor's screen by editing a URL.

`GET /api/rbac-matrix` returns the who-can-see-what table as data. It is readable
without a token because it documents the rules rather than exposing anything: it
says "an ethics committee member cannot list participants", which is a statement
about the system, not about the participants.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app import rbac
from app.db import get_session
from app.kpi import build_dashboard
from app.rbac import CurrentUser, Permission, require

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    trial_id: int | None = Query(
        None, description="restrict to one trial (default: the first trial found)"
    ),
) -> dict:
    """Every tile and block for this user's role, in one round trip.

    The WebSocket at `/ws/dashboard` sends this exact payload again on every
    event, so the live update and a manual refresh can never disagree.
    """
    return build_dashboard(session, user, trial_id)


@router.get("/coordinator/summary")
def get_coordinator_summary(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    trial_id: int | None = Query(None, description="restrict to one trial"),
) -> dict:
    """Live database aggregate summary of the 8 clinical metrics scoped to coordinator's site."""
    from datetime import date, timedelta
    from sqlmodel import func, select
    from app.models import AdverseEvent, Subject, Trial, Visit
    from app.routers.stats import resolve_trial

    trial = resolve_trial(session, trial_id)
    if trial is None:
        return {"tiles": [], "metrics": {}}

    tid = trial.id
    scope_site = user.scope_site_id
    today = date.today()
    fourteen_days_later = today + timedelta(days=14)

    # Scoping expression
    subject_scope = (Subject.site_id == scope_site) if scope_site is not None else True
    ae_scope = (AdverseEvent.site_id == scope_site) if scope_site is not None else True

    # 1. Due in 14 days
    stmt_due_soon = (
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            subject_scope,
            Visit.trial_id == tid,
            Visit.status == "scheduled",
            Visit.scheduled_date.is_not(None),
            Visit.scheduled_date >= today,
            Visit.scheduled_date <= fourteen_days_later,
        )
    )
    due_soon = int(session.exec(stmt_due_soon).one())

    # 2. Past their date
    stmt_overdue = (
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            subject_scope,
            Visit.trial_id == tid,
            Visit.status == "scheduled",
            Visit.scheduled_date.is_not(None),
            Visit.scheduled_date < today,
        )
    )
    overdue = int(session.exec(stmt_overdue).one())

    # 3. Visits completed & total scheduled visits
    stmt_completed = (
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            subject_scope,
            Visit.trial_id == tid,
            Visit.status == "completed",
        )
    )
    completed = int(session.exec(stmt_completed).one())

    stmt_total_visits = (
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            subject_scope,
            Visit.trial_id == tid,
        )
    )
    total_visits = int(session.exec(stmt_total_visits).one())

    # 4. Visits missed
    stmt_missed = (
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            subject_scope,
            Visit.trial_id == tid,
            Visit.status == "missed",
        )
    )
    missed = int(session.exec(stmt_missed).one())

    # 5. In screening
    stmt_in_screening = (
        select(func.count(Subject.id))
        .where(
            subject_scope,
            Subject.trial_id == tid,
            (
                (Subject.status == "screening")
                | (
                    Subject.eligibility_outcome.in_(["pending"])
                    & Subject.status.notin_(["enrolled", "active", "completed", "screen_failed", "withdrawn"])
                )
            ),
        )
    )
    in_screening = int(session.exec(stmt_in_screening).one())

    # 6. Events to code (AEs without MedDRA code)
    stmt_uncoded = (
        select(func.count(AdverseEvent.id))
        .where(
            ae_scope,
            AdverseEvent.trial_id == tid,
            (
                AdverseEvent.meddra_pt_code.is_(None)
                | (AdverseEvent.meddra_pt_code == "")
                | AdverseEvent.meddra_pt_term.is_(None)
                | (AdverseEvent.meddra_pt_term == "")
            ),
        )
    )
    uncoded = int(session.exec(stmt_uncoded).one())

    # 7. Deviations logged & % of visits due
    stmt_deviations = (
        select(func.count(Visit.id))
        .join(Subject, Visit.subject_id == Subject.id)
        .where(
            subject_scope,
            Visit.trial_id == tid,
            Visit.is_protocol_deviation == True,
        )
    )
    deviations = int(session.exec(stmt_deviations).one())
    visits_due = completed + missed
    deviation_rate = round((deviations / visits_due * 100), 1) if visits_due > 0 else 0.0

    # 8. Enrolled here & total screened attempts
    stmt_enrolled = (
        select(func.count(Subject.id))
        .where(
            subject_scope,
            Subject.trial_id == tid,
            (
                Subject.status.in_(["enrolled", "active", "completed"])
                | Subject.enrollment_date.is_not(None)
            ),
        )
    )
    enrolled = int(session.exec(stmt_enrolled).one())

    stmt_screened = (
        select(func.count(Subject.id))
        .where(
            subject_scope,
            Subject.trial_id == tid,
        )
    )
    screened = int(session.exec(stmt_screened).one())

    tiles = [
        {
            "key": "due_soon",
            "label": "Due in 14 days",
            "value": due_soon,
            "hint": "book these now",
            "tone": "warn" if due_soon else "neutral",
        },
        {
            "key": "overdue",
            "label": "Past their date",
            "value": overdue,
            "hint": "still marked scheduled",
            "tone": "bad" if overdue else "good",
        },
        {
            "key": "completed",
            "label": "Visits completed",
            "value": completed,
            "hint": f"of {total_visits} in the schedule",
            "tone": "neutral",
        },
        {
            "key": "missed",
            "label": "Visits missed",
            "value": missed,
            "hint": "window closed without the visit",
            "tone": "bad" if missed else "good",
        },
        {
            "key": "in_screening",
            "label": "In screening",
            "value": in_screening,
            "hint": "awaiting an eligibility decision",
            "tone": "neutral",
        },
        {
            "key": "uncoded",
            "label": "Events to code",
            "value": uncoded,
            "hint": "no MedDRA term yet",
            "tone": "neutral",
        },
        {
            "key": "deviations",
            "label": "Deviations logged",
            "value": deviations,
            "hint": f"{deviation_rate}% of visits due",
            "tone": "neutral",
        },
        {
            "key": "enrolled",
            "label": "Enrolled here",
            "value": enrolled,
            "hint": f"{screened} screened",
            "tone": "neutral",
        },
    ]

    metrics = {
        "due_soon": due_soon,
        "overdue": overdue,
        "completed": completed,
        "total_visits": total_visits,
        "missed": missed,
        "in_screening": in_screening,
        "uncoded": uncoded,
        "deviations": deviations,
        "deviation_rate": deviation_rate,
        "enrolled": enrolled,
        "screened": screened,
    }

    return {
        "site_id": scope_site,
        "trial_id": tid,
        "tiles": tiles,
        "metrics": metrics,
    }


@router.get("/rbac-matrix")
def rbac_matrix() -> dict:
    """Who can do what - the whole table, generated from the rules themselves.

    Generated, not written by hand, so the documentation cannot drift away from
    what the API actually enforces. If a permission is added to a role in
    `rbac.py`, this table changes with it.
    """
    return rbac.matrix()
