"""Participants and their protocol visits.

Every subject record here is de-identified: no name, address, phone or date of
birth is stored, only a year of birth and an age. That is deliberate, and it is
what lets the whole dataset be shown in a demo.

Phase 2 scoping: a Principal Investigator or Coordinator sees only their own
site's participants and those participants' visits. An Ethics Committee member has
no participant access at all - their remit is safety events and deviations, not
browsing who is enrolled.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.enums import UserRole
from app.models import AdverseEvent, Subject, Visit
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate

router = APIRouter(prefix="/api", tags=["subjects"])


def _visible_subject(session: Session, subject_id: int, user: CurrentUser) -> Subject:
    """Fetch a subject, 404 if absent, 403 if it belongs to another site or another patient."""
    subject = session.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"no subject with id {subject_id}")
    if user.role == UserRole.PATIENT.value:
        if user.subject_id is None or user.subject_id != subject_id:
            raise HTTPException(status_code=403, detail="forbidden: patients may only access their own record")
    else:
        assert_site_visible(user, subject.site_id)
    return subject


@router.get("/subjects", response_model=Page[Subject])
def list_subjects(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ)),
    trial_id: int | None = Query(None),
    site_id: int | None = Query(None),
    status: str | None = Query(None, description="e.g. enrolled, completed, withdrawn"),
    arm: str | None = Query(None, description="treatment, placebo, comparator"),
    prakriti: str | None = Query(None, description="Ayurvedic constitutional type"),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Subject]:
    statement = select(Subject).order_by(Subject.subject_code)
    if trial_id is not None:
        statement = statement.where(Subject.trial_id == trial_id)
    if site_id is not None:
        statement = statement.where(Subject.site_id == site_id)
    if status:
        statement = statement.where(Subject.status == status)
    if arm:
        statement = statement.where(Subject.arm == arm)
    if prakriti:
        statement = statement.where(Subject.prakriti == prakriti)
    # Applied last, and unconditionally: a site user who passes ?site_id=3 gets
    # their own site AND site 3, which is nothing. The URL cannot widen the scope.
    statement = scoped(statement, Subject.site_id, user)
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/subjects/{subject_id}", response_model=Subject)
def get_subject(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ)),
) -> Subject:
    return _visible_subject(session, subject_id, user)


@router.get("/subjects/{subject_id}/visits", response_model=list[Visit])
def list_subject_visits(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_READ)),
) -> list[Visit]:
    """One participant's whole visit schedule, in protocol order.

    Not paginated: the schedule is six visits long by design, and a coordinator
    wants to see the whole thing at once.
    """
    _visible_subject(session, subject_id, user)
    return list(
        session.exec(
            select(Visit)
            .where(Visit.subject_id == subject_id)
            .order_by(Visit.visit_number)
        ).all()
    )


@router.get("/subjects/{subject_id}/adverse-events", response_model=list[AdverseEvent])
def list_subject_adverse_events(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ, Permission.AE_READ)),
) -> list[AdverseEvent]:
    _visible_subject(session, subject_id, user)
    return list(
        session.exec(
            select(AdverseEvent)
            .where(AdverseEvent.subject_id == subject_id)
            .order_by(AdverseEvent.onset_date)
        ).all()
    )


@router.get("/visits", response_model=Page[Visit])
def list_visits(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_READ)),
    trial_id: int | None = Query(None),
    subject_id: int | None = Query(None),
    status: str | None = Query(None, description="scheduled, completed, missed..."),
    deviations_only: bool = Query(
        False, description="only visits flagged as a protocol deviation"
    ),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Visit]:
    statement = select(Visit).order_by(Visit.scheduled_date, Visit.visit_number)
    if trial_id is not None:
        statement = statement.where(Visit.trial_id == trial_id)
    if subject_id is not None:
        statement = statement.where(Visit.subject_id == subject_id)
    if status:
        statement = statement.where(Visit.status == status)
    if deviations_only:
        statement = statement.where(Visit.is_protocol_deviation == True)  # noqa: E712
    # If the user is a Patient: strictly isolate to their own subject_id
    if user.role == UserRole.PATIENT.value:
        if user.subject_id is None:
            statement = statement.where(Visit.id == -1)
        else:
            statement = statement.where(Visit.subject_id == user.subject_id)
    elif user.scope_site_id is not None:
        statement = statement.where(
            Visit.subject_id.in_(  # type: ignore[union-attr]
                select(Subject.id).where(Subject.site_id == user.scope_site_id)
            )
        )
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/visits/{visit_id}", response_model=Visit)
def get_visit(
    visit_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.VISIT_READ)),
) -> Visit:
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"no visit with id {visit_id}")
    if user.role == UserRole.PATIENT.value:
        if user.subject_id is None or visit.subject_id != user.subject_id:
            raise HTTPException(status_code=403, detail="forbidden: patients may only access their own visits")
    elif user.scope_site_id is not None:
        subject = session.get(Subject, visit.subject_id)
        assert_site_visible(user, subject.site_id if subject else None)
    return visit
