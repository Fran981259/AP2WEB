"""Migração SQLite local -> Postgres (Neon/Supabase etc.).

Uso:
    DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" \
        backend/.venv/bin/python backend/scripts/migrate_sqlite_to_pg.py

- Cria o schema no Postgres (idempotente) e copia todas as linhas do
  ap2web.db local, preservando os ids.
- Tabelas destino são truncadas antes da cópia (migração substitui tudo).
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Parents must precede children so explicit IDs keep their references valid.
TABLES = (
    "users", "leagues", "teams", "matches", "predictions", "league_models",
    "workers", "jobs", "auth_sessions", "audit_events",
)
ID_TABLES = frozenset({
    "users", "leagues", "teams", "matches", "predictions", "jobs",
    "auth_sessions", "audit_events",
})


def _open_source() -> sqlite3.Connection:
    """Open an explicit SQLite source without changing PostgreSQL app config."""
    default = Path(__file__).resolve().parent.parent / "ap2web.db"
    source_path = Path(os.environ.get("AP2WEB_SQLITE_SOURCE_PATH", default))
    if not source_path.is_file():
        sys.exit(f"SQLite source not found: {source_path}")
    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    return source


def _truncate_destination(dst) -> None:
    """Replace all migratable state, including tables empty in SQLite."""
    quoted = ", ".join(f'"{table}"' for table in TABLES)
    dst.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")


def _copy_table(src, dst, table: str) -> int:
    exists = src.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return 0
    rows = src.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ",".join("%s" for _ in cols)
    collist = ",".join(f'"{column}"' for column in cols)
    sql = f'INSERT INTO "{table}"({collist}) VALUES({placeholders})'
    for row in rows:
        dst.execute(sql, tuple(row[column] for column in cols))
    if table in ID_TABLES:
        dst.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
            f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 1))")
    return len(rows)


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        sys.exit("Defina DATABASE_URL apontando para o Postgres de destino.")
    from app import db
    if db.MODE != "postgres":
        sys.exit("DATABASE_URL não reconhecida — modo ativo: " + db.MODE)

    import psycopg.rows  # noqa: F401 (garante registro do dict_row)
    src = _open_source()

    db.init_db()  # cria schema no destino
    with db._pg_connect() as dst:
        _truncate_destination(dst)
        for table in TABLES:
            copied = _copy_table(src, dst, table)
            print(f"{table}: {copied} linhas migradas")
    src.close()
    print("\n✅ Migração concluída.")


if __name__ == "__main__":
    main()
