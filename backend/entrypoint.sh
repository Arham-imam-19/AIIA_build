#!/bin/sh
# Container startup: bring the schema up to date, then serve the API.
#
# Postgres is marked "healthy" by Docker as soon as it accepts connections, which
# can be a moment before it is actually ready for our first query. So we retry a
# few times rather than dying on a race.
#
# `alembic upgrade head` is safe to run every boot: Alembic records which
# migrations it has already applied in a table called alembic_version, so on the
# second and later starts it looks at the database, sees nothing to do, and exits.

set -e

echo "[entrypoint] waiting for the database..."
attempt=1
until python -c "
import sys
from app.db import check_database
ok, detail = check_database()
print(detail)
sys.exit(0 if ok else 1)
"; do
    if [ "$attempt" -ge 30 ]; then
        echo "[entrypoint] database still unreachable after 30 attempts - giving up"
        exit 1
    fi
    echo "[entrypoint] not ready yet (attempt $attempt/30), retrying in 2s"
    attempt=$((attempt + 1))
    sleep 2
done

echo "[entrypoint] applying migrations (alembic upgrade head)"
alembic upgrade head

echo "[entrypoint] seeding demo data if empty"
python scripts/seed.py || true

echo "[entrypoint] starting API on :8000"
# exec replaces this shell with uvicorn, so Ctrl-C and `docker compose stop`
# reach the server directly instead of being swallowed by the script.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
