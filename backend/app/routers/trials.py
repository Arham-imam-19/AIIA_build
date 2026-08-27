"""Trials and the sites that run them.

Phase 2 added the guard on each endpoint. A Principal Investigator or Coordinator
sees only their own hospital in `/api/sites`, and asking for another site's row by
id is a 403 rather than an empty answer - see `app/rbac.py` for why that
distinction matters.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, SQLModel, select

from app.db import get_session
from app.models import Site, Subject, Trial
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
    scoped,
)
from app.routers.common import Page, limit_param, offset_param, paginate

router = APIRouter(prefix="/api", tags=["trials"])


@router.get("/trials", response_model=Page[Trial])
def list_trials(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
    status: str | None = Query(None, description="filter by trial status"),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Trial]:
    """The trial itself is visible to every role - a site investigator still needs
    to read the protocol they are running."""
    statement = select(Trial).order_by(Trial.protocol_number)
    if status:
        statement = statement.where(Trial.status == status)
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/trials/{trial_id}", response_model=Trial)
def get_trial(
    trial_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ)),
) -> Trial:
    trial = session.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"no trial with id {trial_id}")
    return trial


@router.get("/sites", response_model=Page[Site])
def list_sites(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SITE_READ)),
    trial_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Site]:
    statement = select(Site).order_by(Site.site_code)
    if trial_id is not None:
        statement = statement.where(Site.trial_id == trial_id)
    if status:
        statement = statement.where(Site.status == status)
    # A site user sees one site: their own. The scoping column here is the site's
    # own primary key rather than a site_id foreign key.
    statement = scoped(statement, Site.id, user)
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/sites/{site_id}", response_model=Site)
def get_site(
    site_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SITE_READ)),
) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"no site with id {site_id}")
    assert_site_visible(user, site.id)
    return site


@router.get("/sites/{site_id}/subjects", response_model=Page[Subject])
def list_site_subjects(
    site_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SITE_READ, Permission.SUBJECT_READ)),
    limit: int = limit_param(),
    offset: int = offset_param(),
) -> Page[Subject]:
    """The participants at one site.

    Needs both permissions: you must be allowed to see the site *and* to see
    participants. That is why an Ethics Committee member, who has site access but
    deliberately no participant access, gets 403 here.
    """
    if session.get(Site, site_id) is None:
        raise HTTPException(status_code=404, detail=f"no site with id {site_id}")
    assert_site_visible(user, site_id)
    statement = (
        select(Subject).where(Subject.site_id == site_id).order_by(Subject.subject_code)
    )
    total, items = paginate(session, statement, limit, offset)
    return Page(total=total, limit=limit, offset=offset, items=items)


class CreateSiteRequest(SQLModel):
    trial_id: int
    site_code: str
    name: str
    city: str
    state: str
    country: str = "India"
    pi_name: str
    pi_email: str | None = None
    contact_phone: str | None = None
    status: str = "activated"
    target_enrollment: int = 0


@router.post("/sites", response_model=Site, status_code=201)
def create_site(
    body: CreateSiteRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.INSTITUTION_MANAGE)),
) -> Site:
    """Primary Admin creates a new participating Institution / Site."""
    trial = session.get(Trial, body.trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"trial {body.trial_id} not found")

    existing = session.exec(select(Site).where(Site.site_code == body.site_code)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"site code {body.site_code} already exists")

    site = Site(**body.model_dump())
    session.add(site)
    session.commit()
    session.refresh(site)
    return site
