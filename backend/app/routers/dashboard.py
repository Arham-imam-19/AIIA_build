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


@router.get("/rbac-matrix")
def rbac_matrix() -> dict:
    """Who can do what - the whole table, generated from the rules themselves.

    Generated, not written by hand, so the documentation cannot drift away from
    what the API actually enforces. If a permission is added to a role in
    `rbac.py`, this table changes with it.
    """
    return rbac.matrix()
