"""Database engine and session handling."""

from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app import config

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the shared engine, building it on first use.

    Deliberately lazy: building the engine can fail (bad DATABASE_URL, missing
    driver), and if that happened at import time the whole API would die with a
    traceback instead of coming up and showing a red database light on the
    dashboard. During a live demo, a running app that says "database
    unreachable" beats a container that refuses to boot.
    """
    global _engine
    if _engine is None:
        # SQLite (the no-Docker fallback) needs one extra flag because FastAPI
        # touches the connection from more than one thread. Postgres does not.
        connect_args = (
            {"check_same_thread": False}
            if config.DATABASE_URL.startswith("sqlite")
            else {}
        )
        _engine = create_engine(
            config.DATABASE_URL,
            echo=False,
            # Recycle connections before Postgres drops them as idle.
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _engine


def create_all_tables() -> None:
    """Build the schema straight from the models, skipping Alembic.

    Only for tests, which want a throwaway SQLite database in a temp directory.
    The application never calls this: in a real deployment the schema is owned by
    `alembic upgrade head`, and letting the app create tables too would mean two
    competing definitions of the truth.
    """
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: hands each request its own database session."""
    with Session(get_engine()) as session:
        yield session


def check_database() -> tuple[bool, str]:
    """Run the cheapest possible query to confirm the database is reachable.

    Returns (ok, detail) instead of raising, so /api/health can report a red
    light rather than returning a 500.
    """
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # noqa: BLE001 - health check reports, never raises
        return False, f"{type(exc).__name__}: {exc}"


def describe_schema() -> tuple[list[str], str | None]:
    """Return (table names, current Alembic revision).

    The revision is the id of the last migration applied to this database, which
    Alembic stores in a table called alembic_version. Comparing it to what the
    code expects is how you catch "the container is running last week's schema" -
    the usual cause of a sudden "column does not exist".

    Like `check_database`, this reports problems instead of raising: it is called
    from the health endpoint.
    """
    try:
        engine = get_engine()
        table_names = [
            name for name in inspect(engine).get_table_names()
            if name != "alembic_version"
        ]
        revision: str | None = None
        if "alembic_version" in inspect(engine).get_table_names():
            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).first()
                revision = row[0] if row else None
        return table_names, revision
    except Exception:  # noqa: BLE001 - health check reports, never raises
        return [], None
