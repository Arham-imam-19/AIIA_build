"""Alembic runtime configuration.

Two things happen here:

1. The database URL comes from `app.config` (i.e. from the DATABASE_URL
   environment variable), not from alembic.ini. One source of truth.

2. `app.models` is imported for its side effect: importing the models registers
   every table on `SQLModel.metadata`. Without that import, `alembic revision
   --autogenerate` would compare the database against an empty schema and
   cheerfully propose dropping all your tables.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app import config as app_config
from app import models  # noqa: F401  - registers all tables on SQLModel.metadata

alembic_config = context.config

# Point Alembic at whichever database the application itself is configured for.
alembic_config.set_main_option("sqlalchemy.url", app_config.DATABASE_URL)

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it.

    Useful when a database administrator has to review and apply the change by
    hand - which is exactly how a regulated production system often works.
    """
    context.configure(
        url=alembic_config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply the migrations."""
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite cannot ALTER most things in place; batch mode makes Alembic
            # rebuild the table instead. Harmless on Postgres, essential for the
            # no-Docker fallback.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
