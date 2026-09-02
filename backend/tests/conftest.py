"""Shared test machinery: a seeded SQLite database and authenticated clients.

Everything here runs without Docker and without Postgres:

    cd backend && pytest -q

Three problems this file solves, each of which bit us during Phase 2.

**Seeding is the slow part.** The generator builds a whole trial and bcrypt
hashes a password, so doing it per module wasted seconds. Instead it happens
*once* per test session into a template file, and each module gets its own copy
of that file. Copying a 1 MB SQLite file is instant, so modules stay isolated
(one that writes rows cannot break another's counts) without paying to reseed.

**`app.dependency_overrides` is global.** It is one dict on one app object, so two
fixtures that both override `get_session` fight over it - whichever client was
built last wins, and the other silently starts querying the wrong database.
`ScopedClient` fixes that by re-installing its own overrides immediately before
every request, so which client you call decides which database you hit.

**Phase 2 put a lock on every endpoint.** The Phase 1 tests were written against
an open API and would now all return 401. Rather than rewriting them, the seeded
client carries an Administrator's bearer token by default: the admin holds every
permission and is not site-scoped, so every existing assertion still describes
what an unrestricted caller sees. Tests that care about *restriction* ask for a
role-specific client instead.
"""

from __future__ import annotations

import importlib.util
import shutil
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app import security, synthetic
from app.db import get_session
from app.enums import UserRole
from app.main import app
from app.models import User
from app.rbac import CurrentUser, get_current_user

# The same fixed "today" the generator tests use, so every count is deterministic.
# Without it the seed would drift each day: how many visits are already due
# depends on the date, and so does the deviation rate.
REFERENCE = date(2026, 8, 25)


# ----------------------------------------------------------------- the database


def load_seed_script():
    """Import scripts/seed.py, which lives outside the app package.

    Its location differs between the container and a laptop: docker-compose
    mounts ./scripts to /app/scripts (next to this test's parent), while on the
    host it sits at the repository root, one level above backend/. Try both.
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "scripts" / "seed.py",  # in the container: /app/scripts
        here.parents[2] / "scripts" / "seed.py",  # on the host: <repo>/scripts
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location("seed_script", path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise AssertionError(f"cannot find seed.py; looked in {[str(p) for p in candidates]}")


def make_engine(path: Path) -> sa.Engine:
    """An engine on a SQLite file, with the schema in place.

    `check_same_thread=False` because TestClient runs the app on a different
    thread than the test, and SQLite objects to that by default.
    """
    engine = sa.create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="session")
def seeded_template(tmp_path_factory) -> Path:
    """One seeded database file, built once for the whole test session."""
    path = tmp_path_factory.mktemp("aiia-template") / "template.db"
    engine = make_engine(path)
    with Session(engine) as session:
        load_seed_script().seed(session, REFERENCE, synthetic.DEFAULT_SEED)
    # Release the file before anyone copies it.
    engine.dispose()
    return path


@pytest.fixture(scope="module")
def seeded_engine(seeded_template, tmp_path_factory) -> sa.Engine:
    """A private copy of the seeded database, one per test module."""
    path = tmp_path_factory.mktemp("aiia-db") / "seeded.db"
    shutil.copyfile(seeded_template, path)
    return make_engine(path)


@pytest.fixture(scope="module")
def empty_engine(tmp_path_factory) -> sa.Engine:
    """Migrated but with no rows - what you see before running the seed script."""
    return make_engine(tmp_path_factory.mktemp("aiia-db") / "empty.db")


# ------------------------------------------------------------------- the client


class ScopedClient(TestClient):
    """A TestClient that keeps its own dependency overrides installed.

    See the module docstring: overrides live in one global dict, so they are
    re-applied per request rather than once at construction. `websocket_connect`
    needs the same treatment and does *not* go through `request()` - Starlette
    calls httpx's `request` directly - so it is overridden separately.
    """

    def __init__(self, *args, overrides: dict, **kwargs):
        super().__init__(*args, **kwargs)
        self._overrides = overrides

    def install(self) -> None:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self._overrides)

    def request(self, *args, **kwargs):
        self.install()
        return super().request(*args, **kwargs)

    def websocket_connect(self, *args, **kwargs):
        self.install()
        return super().websocket_connect(*args, **kwargs)


def session_override(engine: sa.Engine):
    def override():
        with Session(engine) as session:
            yield session

    return override


def token_for(engine: sa.Engine, role: str) -> str:
    """Mint a real signed token for the first seeded user with this role.

    Minted rather than obtained from `POST /api/auth/login` on purpose: the token
    is identical either way, and skipping the bcrypt verification keeps the suite
    fast. `test_auth.py` exercises the real login path, which is where that
    belongs.
    """
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.role == role).order_by(User.id)
        ).first()
        assert user is not None, f"no seeded user with role {role}"
        return token_for_user(user)


def token_for_user(user: User) -> str:
    """Mint a token for one specific user row - used to pick a *particular* site."""
    token, _expires, _jti = security.create_access_token(
        user_id=user.id, email=user.email, role=user.role, site_id=user.site_id
    )
    return token


def users_by_role(engine: sa.Engine, role: str) -> list[User]:
    """Every seeded user with this role, oldest first.

    Site-scoping tests need two people in the same job at *different* hospitals,
    which is exactly what the seed provides (one investigator per site).
    """
    with Session(engine) as session:
        return list(
            session.exec(select(User).where(User.role == role).order_by(User.id)).all()
        )


def client_for(engine: sa.Engine, role: str | None = None) -> ScopedClient:
    """A client pointed at `engine`, signed in as the first user of `role`.

    `role=None` means no Authorization header at all - for testing that the lock
    is actually on the door.
    """
    headers = {}
    if role is not None:
        headers["Authorization"] = f"Bearer {token_for(engine, role)}"
    return ScopedClient(
        app, overrides={get_session: session_override(engine)}, headers=headers
    )


def client_for_user(engine: sa.Engine, user: User) -> ScopedClient:
    """A client signed in as one specific person.

    Needed wherever *which* site matters: "the investigator" is four different
    people with four different scopes.
    """
    return ScopedClient(
        app,
        overrides={get_session: session_override(engine)},
        headers={"Authorization": f"Bearer {token_for_user(user)}"},
    )


@pytest.fixture(scope="module")
def client(seeded_engine) -> ScopedClient:
    """The everyday client: seeded data, signed in as an Administrator."""
    test_client = client_for(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def anonymous_client(seeded_engine) -> ScopedClient:
    """Seeded data, no token - every protected endpoint should refuse this."""
    test_client = client_for(seeded_engine)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def empty_client(empty_engine) -> ScopedClient:
    """An un-seeded database.

    There are no users here, so a real token cannot resolve to anybody - the
    identity is supplied directly instead. That still exercises the endpoints'
    "nothing is seeded yet" behaviour, which is the point of this fixture.
    """
    nobody = CurrentUser(
        id=1,
        email="admin@example.test",
        full_name="Test Administrator",
        role=UserRole.ADMIN.value,
    )

    async def override_user() -> CurrentUser:
        return nobody

    test_client = ScopedClient(
        app,
        overrides={
            get_session: session_override(empty_engine),
            get_current_user: override_user,
        },
    )
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def role_clients(seeded_engine) -> dict[str, ScopedClient]:
    """One signed-in client per role, keyed by role string."""
    clients = {
        role.value: client_for(seeded_engine, role.value)
        for role in (
            UserRole.ADMIN,
            UserRole.INSTITUTION_ADMIN,
            UserRole.PRINCIPAL_INVESTIGATOR,
            UserRole.COORDINATOR,
            UserRole.PATIENT,
            UserRole.SPONSOR,
            UserRole.ETHICS_COMMITTEE,
            UserRole.REGULATOR,
        )
    }
    yield clients
    app.dependency_overrides.clear()
