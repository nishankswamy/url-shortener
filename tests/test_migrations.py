"""Migrations have to run against a database that already has data in it.

The first version of the is_bot migration passed here on an empty database and
would have failed on any real one:

    Cannot add a NOT NULL column with default value NULL
"""

import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parent.parent


def alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )


@pytest.fixture
def db(tmp_path):
    return tmp_path / "migration-test.db"


def test_migrations_run_from_scratch(db):
    result = alembic(db, "upgrade", "head")
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    tables = set(sa.inspect(engine).get_table_names())
    assert {"links", "clicks", "alembic_version"} <= tables


def test_migrations_run_against_populated_tables(db):
    """The regression that matters. Stop at the revision before is_bot, insert
    rows, then migrate forward."""
    assert alembic(db, "upgrade", "289d5fe89487").returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO links (short_code, target_url, is_custom, created_at) "
                "VALUES ('abc', 'https://example.com', 0, '2026-01-01T00:00:00')"
            )
        )
        for agent in ("Mozilla/5.0", None):
            conn.execute(
                sa.text(
                    "INSERT INTO clicks (link_id, clicked_at, referrer, user_agent) "
                    "VALUES (1, '2026-01-01T00:00:00', NULL, :agent)"
                ),
                {"agent": agent},
            )

    result = alembic(db, "upgrade", "head")
    assert result.returncode == 0, result.stderr

    with engine.begin() as conn:
        rows = conn.execute(sa.text("SELECT user_agent, is_bot FROM clicks")).all()

    # Existing rows survive, and the one with no user agent is backfilled.
    assert sorted((agent or "", bool(flag)) for agent, flag in rows) == [
        ("", True),
        ("Mozilla/5.0", False),
    ]


def test_no_drift_between_models_and_migrations(db):
    """Catches a model change that nobody wrote a migration for."""
    assert alembic(db, "upgrade", "head").returncode == 0
    result = alembic(db, "check")
    assert "No new upgrade operations detected" in result.stdout + result.stderr


def test_downgrade_is_reversible(db):
    assert alembic(db, "upgrade", "head").returncode == 0
    assert alembic(db, "downgrade", "-1").returncode == 0
    assert alembic(db, "upgrade", "head").returncode == 0
