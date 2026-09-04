"""HTTP routers, grouped along the same seams as the project's features.

    auth.py        log in, log out, who am I         (Phase 2)
    trials.py      the trial and its sites          (who is running what, where)
    subjects.py    participants and their visits    (the enrolment funnel)
    safety.py      adverse events                   (Feature 2 extends this)
    compliance.py  the audit trail                  (Feature 3 extends this)
    stats.py       the aggregate numbers the dashboards draw
    dashboard.py   one role-shaped payload per persona, plus the RBAC matrix
    live.py        the WebSocket that pushes a fresh dashboard on every change
    simulate.py    demo tooling that writes real rows so the live update is real
    patient_requests.py patient inquiries and communications

Phase 1 was read-only. Phase 2 added authentication, so every endpoint above now
needs a token, and the first writes appear - in `simulate.py`, each one paired with
an audit entry, because in a regulated system every change has to be attributable
to a named user.
"""

from app.routers import (
    ingest,
    auth,
    compliance,
    dashboard,
    econsent,
    exports,
    live,
    patient_requests,
    safety,
    simulate,
    stats,
    subjects,
    trials,
)

ALL_ROUTERS = (
    # Auth first so /api/auth/login appears at the top of the generated docs -
    # it is the first thing anybody reading them needs.
    auth.router,
    dashboard.router,
    trials.router,
    subjects.router,
    safety.router,
    patient_requests.router,
    econsent.router,
    compliance.router,
    exports.router,
    stats.router,
    simulate.router,
    ingest.router,
    live.router,
)
