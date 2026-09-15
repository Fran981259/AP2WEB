"""Unit coverage for the SQLite-to-PostgreSQL migration plan.

The actual PostgreSQL connection is exercised only by the opt-in Docker gate.
"""
import importlib.util
import sqlite3
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "backend/scripts/migrate_sqlite_to_pg.py"
SPEC = importlib.util.spec_from_file_location("migrate_sqlite_to_pg", SCRIPT)
migration = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(migration)


class _Destination:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))


def test_migration_plan_includes_operational_tables():
    assert {"workers", "jobs", "auth_sessions", "audit_events", "execution_events"} <= set(migration.TABLES)
    assert "schema_migrations" not in migration.TABLES
    dst = _Destination()
    migration._truncate_destination(dst)
    assert len(dst.calls) == 1
    sql = dst.calls[0][0]
    assert sql.startswith("TRUNCATE TABLE")
    assert '"auth_sessions"' in sql
    assert "RESTART IDENTITY CASCADE" in sql


def test_copy_table_preserves_explicit_ids_and_resets_sequence():
    src = sqlite3.connect(":memory:")
    src.row_factory = sqlite3.Row
    src.execute("CREATE TABLE users (id INTEGER, username TEXT)")
    src.execute("INSERT INTO users VALUES (7, 'alice')")
    dst = _Destination()

    assert migration._copy_table(src, dst, "users") == 1
    assert dst.calls[0][1] == (7, "alice")
    assert 'INSERT INTO "users"("id","username")' in dst.calls[0][0]
    assert "setval" in dst.calls[1][0]


def test_copy_execution_events_resets_its_sequence():
    src = sqlite3.connect(":memory:")
    src.row_factory = sqlite3.Row
    src.execute("CREATE TABLE execution_events (id INTEGER, execution_id TEXT)")
    src.execute("INSERT INTO execution_events VALUES (9, 'execution-1')")
    dst = _Destination()

    assert migration._copy_table(src, dst, "execution_events") == 1
    assert dst.calls[0][1] == (9, "execution-1")
    assert "setval" in dst.calls[1][0]


def test_copy_empty_table_does_not_issue_insert_or_sequence_query():
    src = sqlite3.connect(":memory:")
    src.row_factory = sqlite3.Row
    src.execute("CREATE TABLE workers (worker_id TEXT)")
    dst = _Destination()

    assert migration._copy_table(src, dst, "workers") == 0
    assert dst.calls == []


def test_copy_missing_legacy_table_is_treated_as_empty():
    src = sqlite3.connect(":memory:")
    dst = _Destination()

    assert migration._copy_table(src, dst, "audit_events") == 0
    assert dst.calls == []


def test_open_source_uses_explicit_path(tmp_path, monkeypatch):
    source_path = tmp_path / "source.db"
    sqlite3.connect(source_path).close()
    monkeypatch.setenv("AP2WEB_SQLITE_SOURCE_PATH", str(source_path))

    source = migration._open_source()
    try:
        assert source.execute("SELECT 1").fetchone()[0] == 1
    finally:
        source.close()
