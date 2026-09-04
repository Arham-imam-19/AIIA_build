"""FastAPI application entrypoint.

Phase 1 scope: the seven core tables, real Alembic migrations, a synthetic
Ayurveda trial seeded into them, and read-only endpoints over the result.

Phase 2 adds authentication (JWT), role-based access control, one dashboard per
persona, and a WebSocket that pushes a fresh dashboard whenever the data changes.
No new tables, so no new migration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.db import check_database, describe_schema
from app.events import bus
from app.routers import ALL_ROUTERS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once on startup and once on shutdown."""
    ok, detail = check_database()
    if ok:
        print(f"[startup] database ready ({config.DATABASE_URL.split('@')[-1]})")
        # The schema is built by `alembic upgrade head` in entrypoint.sh, not
        # here. Calling create_all() at startup would quietly conjure any table a
        # migration forgot, which is precisely the drift the migrations exist to
        # prevent - and it would work locally while failing in a real deployment
        # where the app has no permission to create tables.
        tables, revision = describe_schema()
        if not tables:
            print("[startup] WARNING no tables found - have the migrations run?")
        else:
            print(f"[startup] schema at revision {revision or 'unknown'} "
                  f"({len(tables)} tables)")
    else:
        # Don't crash the API just because the DB is slow to come up - the health
        # endpoint will show the problem and uvicorn --reload picks it up later.
        print(f"[startup] WARNING database unreachable: {detail}")

    # Connect the live-update bus. This never raises: if Redis is missing it drops
    # to an in-process fan-out, which behaves identically for a single backend
    # container and simply cannot broadcast across several.
    await bus.start()
    print(f"[startup] live updates via {bus.backend} ({bus.detail})")

    yield

    await bus.stop()
    print("[shutdown] bye")


app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description=(
        "Real-time, GCP-compliant Clinical Trial Management System for Ayurveda "
        "research (Ministry of Ayush / AIIA). Synthetic data only."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"^https://.*\.onrender\.com$|^https://.*\.vercel\.app$|^http://localhost(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in ALL_ROUTERS:
    app.include_router(router)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Plain landing response, handy for a quick curl."""
    return {
        "name": config.APP_NAME,
        "version": config.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
        "stats": "/api/stats",
    }


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Liveness + database check. The frontend polls this for its status light."""
    db_ok, db_detail = check_database()
    tables, revision = describe_schema() if db_ok else ([], None)
    return {
        "status": "ok" if db_ok and tables else "degraded",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "environment": config.APP_ENV,
        "database": {"ok": db_ok, "detail": db_detail},
        "schema": {
            "tables": len(tables),
            # Which migration the database is currently at. Mismatched with the
            # code is the classic cause of "column does not exist" in a deploy.
            "migration_revision": revision,
        },
        "live": {
            # "redis" or "in-process". Worth surfacing: it is the difference
            # between updates that cross containers and updates that don't.
            "backend": bus.backend,
            "detail": bus.detail,
            "subscribers": bus.subscriber_count,
        },
    }


@app.get("/api/info", tags=["meta"])
def info() -> dict:
    """Static project metadata, used by the frontend to prove the API call
    round-trips real data (not a hardcoded string in the React app)."""
    return {
        "project": "AIIA Clinical Trials Dashboard",
        "problem_statement": "SIH26046",
        "phase": 2,
        "phase_name": "Authentication, role-based access control and live dashboards",
        "features": [
            "AI Data-Harmonization Engine (CDISC SDTM + FHIR)",
            "Real-time Pharmacovigilance (adverse-event NLP + signal alerts)",
            "Compliance-by-design (CTRI, NDCT 2019, audit trail, e-signatures)",
            "Role-based live KPI cockpits over WebSocket",
            "Ayurveda-native data model (prakriti, formulations, posology)",
        ],
        "roles": [
            "Principal Investigator",
            "Sponsor",
            "Ethics Committee",
            "Regulator",
            "Clinical Research Coordinator",
        ],
        "auth": {
            "login": "/api/auth/login",
            "me": "/api/auth/me",
            "logout": "/api/auth/logout",
            # Only answers in development; a 404 in any other environment.
            "demo_users": "/api/auth/demo-users",
            "rbac_matrix": "/api/rbac-matrix",
        },
        "live": {"websocket": "/ws/dashboard?token=<access token>"},
        "data_notice": "All data in this system is synthetic. No real patient data.",
    }
