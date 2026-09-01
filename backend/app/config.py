"""Application settings, read from environment variables.

Kept deliberately plain (os.getenv, no settings library) so it is obvious where
every value comes from.
"""

import os

APP_NAME = "AIIA Clinical Trials Dashboard"
APP_VERSION = "0.1.0"
APP_ENV = os.getenv("APP_ENV", "development")

# Where the data lives.
#
# Inside Docker this points at the "db" service. If you run the backend directly
# on your laptop without Docker, set DATABASE_URL to a local Postgres, or to
# "sqlite:///./aiia_dev.db" for a quick zero-setup smoke test.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://aiia:aiia@db:5432/aiia_ctms",
)

# Used from Phase 2 onward to push live KPI updates over WebSocket.
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# --- Phase 2: authentication -------------------------------------------------

# The secret the server signs login tokens with. Anyone holding it can mint a
# token for any user, so a real deployment MUST set this from a secrets manager.
# The default exists only so `docker compose up` works with no configuration -
# it is printed as a warning at startup outside development.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me")

# HS256 = sign with a shared secret (as opposed to a public/private key pair).
# Right choice here because one service both issues and checks the tokens.
JWT_ALGORITHM = "HS256"

# How long a login lasts. Twelve hours is generous for a demo day: log in once
# in the morning, present all afternoon without being kicked out mid-question.
ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "720"))

# The password every seeded demo persona shares, so five logins are memorable
# during a five-minute pitch. Synthetic users only - there is no real account
# anywhere in this system.
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "aiia2026")

# Development-only conveniences: the /api/auth/demo-users endpoint that lists the
# personas and their shared password, and the one-click persona buttons on the
# login screen. Both switch off automatically when APP_ENV is not development.
IS_DEVELOPMENT = APP_ENV == "development"

# Browser origins allowed to call this API. The Vite dev server proxies /api to
# the backend, so in the normal setup this list is a safety net rather than a
# requirement.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
