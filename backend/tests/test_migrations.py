"""Guard against the schema and the models drifting apart.

Two descriptions of the database exist in this project:

1. `app/models/*.py` - what the Python code believes the tables look like.
2. `alembic/versions/*.py` - what actually gets built in a real database.

Nothing forces those to agree. Add a column to a model, forget the migration,
and every test that uses `create_all()` still passes while the real Postgres
container is missing the column. These tests close that gap: they run the
migrations into a throwaway SQLite file and compare the result, table by table
and column by column, against the models.

SQLite rather than Postgres so the test needs no running database. The two
disagree on exotic types, so the comparison deliberately checks names,
nullability and broad type family - not the exact SQL type string.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import SQLModel

from app import models  # noqa: F401  - registers every table on the metadata

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _load_migrations() -> list:
    """Import every migration script, ordered by filename.

    Filenames start with a zero-padded revision number (0001_, 0002_, ...) so
    sorting them alphabetically is the same as sorting them by revision.
    """
    scripts = []
    for path in sorted(MIGRATIONS_DIR.glob("[0-9]*.py")):
        spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        scripts.append(module)
    return scripts


def _run(engine: sa.Engine, direction: str) -> None:
    """Apply every migration's upgrade() or downgrade() against `engine`.

    Alembic's `op.create_table(...)` calls normally work because the `alembic`
    command installs a hidden proxy pointing at the live connection. Here we
    install that proxy ourselves, which lets the migration functions be called
    like ordinary Python.
    """
    scripts = _load_migrations()
    if direction == "downgrade":
        scripts = list(reversed(scripts))
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for script in scripts:
                getattr(script, direction)()


@pytest.fixture(scope="module")
def migrated_engine(tmp_path_factory) -> sa.Engine:
    """A SQLite database built purely by running the migrations."""
    db_path = tmp_path_factory.mktemp("migrations") / "schema.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    _run(engine, "upgrade")
    return engine


# --------------------------------------------------------------------- shape


def test_migrations_directory_is_not_empty() -> None:
    assert _load_migrations(), "no migration scripts found in alembic/versions/"


def test_migration_revisions_form_a_single_chain() -> None:
    """Exactly one root, and every other revision points at its predecessor.

    A branch here means `alembic upgrade head` fails with "multiple heads",
    which is a confusing error to hit five minutes before a demo.
    """
    scripts = _load_migrations()
    roots = [s for s in scripts if s.down_revision is None]
    assert len(roots) == 1, "expected exactly one migration with down_revision = None"

    revisions = [s.revision for s in scripts]
    assert len(set(revisions)) == len(revisions), "duplicate revision ids"

    for previous, current in zip(scripts, scripts[1:]):
        assert current.down_revision == previous.revision, (
            f"revision {current.revision} should follow {previous.revision}"
        )


def test_migrations_create_every_model_table(migrated_engine: sa.Engine) -> None:
    built = set(sa.inspect(migrated_engine).get_table_names())
    expected = set(SQLModel.metadata.tables)
    assert expected - built == set(), "tables defined in models but never migrated"
    assert built - expected == set(), "tables created by migrations with no model"


def test_seven_core_tables_exist(migrated_engine: sa.Engine) -> None:
    """The Phase 1 data model, spelled out so a rename cannot pass silently."""
    built = set(sa.inspect(migrated_engine).get_table_names())
    assert built == {
        "trials",
        "sites",
        "users",
        "subjects",
        "visits",
        "adverse_events",
        "audit_logs",
    }


# ------------------------------------------------------------------- columns


def test_migrations_create_every_model_column(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)
    problems: list[str] = []

    for table_name, table in SQLModel.metadata.tables.items():
        built = {c["name"] for c in inspector.get_columns(table_name)}
        expected = set(table.columns.keys())
        for missing in sorted(expected - built):
            problems.append(f"{table_name}.{missing} is in the model, not the migration")
        for extra in sorted(built - expected):
            problems.append(f"{table_name}.{extra} is in the migration, not the model")

    assert not problems, "model/migration column drift:\n  " + "\n  ".join(problems)


def test_column_nullability_matches_the_models(migrated_engine: sa.Engine) -> None:
    """A column that is NOT NULL in the model but nullable in the database (or
    the reverse) is the drift that bites hardest: inserts succeed in tests and
    fail in the container, or vice versa.
    """
    inspector = sa.inspect(migrated_engine)
    problems: list[str] = []

    for table_name, table in SQLModel.metadata.tables.items():
        built = {c["name"]: c for c in inspector.get_columns(table_name)}
        for name, column in table.columns.items():
            if name not in built:
                continue  # reported by the column test above
            if column.primary_key:
                continue  # SQLite reports INTEGER PRIMARY KEY inconsistently
            if bool(built[name]["nullable"]) != bool(column.nullable):
                problems.append(
                    f"{table_name}.{name}: model nullable={column.nullable}, "
                    f"migration nullable={built[name]['nullable']}"
                )

    assert not problems, "nullability drift:\n  " + "\n  ".join(problems)


def _type_family(type_: object) -> str:
    """Collapse a SQL type to a coarse family.

    VARCHAR(200) vs VARCHAR(300) is a judgement call we do not want to fail on;
    VARCHAR vs INTEGER absolutely is.
    """
    for family, klass in (
        ("bool", sa.Boolean),
        ("int", sa.Integer),
        ("float", sa.Float),
        ("datetime", sa.DateTime),
        ("date", sa.Date),
        ("string", sa.String),
    ):
        if isinstance(type_, klass):
            return family
    return type(type_).__name__.lower()


def test_column_type_families_match_the_models(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)
    problems: list[str] = []

    for table_name, table in SQLModel.metadata.tables.items():
        built = {c["name"]: c for c in inspector.get_columns(table_name)}
        for name, column in table.columns.items():
            if name not in built:
                continue
            want = _type_family(column.type)
            got = _type_family(built[name]["type"])
            if want != got:
                problems.append(f"{table_name}.{name}: model {want}, migration {got}")

    assert not problems, "column type drift:\n  " + "\n  ".join(problems)


# --------------------------------------------------------- keys and indexes


def test_every_model_foreign_key_exists_in_the_migration(
    migrated_engine: sa.Engine,
) -> None:
    """Foreign keys are what stop an adverse event pointing at subject 9999."""
    inspector = sa.inspect(migrated_engine)
    problems: list[str] = []

    for table_name, table in SQLModel.metadata.tables.items():
        built = {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys(table_name)
        }
        for constraint in table.foreign_key_constraints:
            key = (
                tuple(c.name for c in constraint.columns),
                constraint.referred_table.name,
            )
            if key not in built:
                problems.append(
                    f"{table_name}: missing foreign key {key[0]} -> {key[1]}"
                )

    assert not problems, "foreign key drift:\n  " + "\n  ".join(problems)


def test_every_model_index_exists_in_the_migration(migrated_engine: sa.Engine) -> None:
    """Indexes are the difference between a dashboard that loads and one that
    hangs. Missing one is invisible until the data grows.
    """
    inspector = sa.inspect(migrated_engine)
    problems: list[str] = []

    for table_name, table in SQLModel.metadata.tables.items():
        built = {tuple(i["column_names"]) for i in inspector.get_indexes(table_name)}
        # Unique constraints are enforced by a unique index in our migration.
        built |= {
            tuple(u["column_names"])
            for u in inspector.get_unique_constraints(table_name)
        }
        for index in table.indexes:
            key = tuple(c.name for c in index.columns)
            if key not in built:
                problems.append(f"{table_name}: missing index on {key}")

    assert not problems, "index drift:\n  " + "\n  ".join(problems)


def test_unique_columns_are_unique_in_the_migration(
    migrated_engine: sa.Engine,
) -> None:
    """protocol_number, ctri_number, subject_code and email must be unique.

    Two subjects sharing a code is a data-integrity incident in a real trial,
    not a cosmetic bug.
    """
    inspector = sa.inspect(migrated_engine)
    expected = {
        ("trials", "protocol_number"),
        ("trials", "ctri_number"),
        ("users", "email"),
        ("subjects", "subject_code"),
    }
    for table_name, column_name in expected:
        unique_columns = {
            tuple(i["column_names"])
            for i in inspector.get_indexes(table_name)
            if i["unique"]
        } | {
            tuple(u["column_names"])
            for u in inspector.get_unique_constraints(table_name)
        }
        assert (column_name,) in unique_columns, (
            f"{table_name}.{column_name} should be unique in the migration"
        )


# ----------------------------------------------------------------- downgrade


def test_downgrade_removes_every_table(tmp_path) -> None:
    """A migration you cannot reverse is a migration you cannot test twice."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'roundtrip.db'}")
    _run(engine, "upgrade")
    assert sa.inspect(engine).get_table_names()
    _run(engine, "downgrade")
    assert sa.inspect(engine).get_table_names() == []


def test_upgrade_is_repeatable_after_downgrade(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'repeat.db'}")
    _run(engine, "upgrade")
    first = sorted(sa.inspect(engine).get_table_names())
    _run(engine, "downgrade")
    _run(engine, "upgrade")
    assert sorted(sa.inspect(engine).get_table_names()) == first
