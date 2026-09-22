"""Camada de banco dual-engine do AP2WEB.

- SQLite (padrão local): comportamento idêntico ao original.
- Postgres (Neon/Supabase etc.): ativado pela env var DATABASE_URL.
  O SQL escrito no projeto continua em dialeto SQLite (`?`, date(),
  datetime('now')) — a camada traduz em tempo de execução (ML Skill v1.1 §20.1:
  fonte única; nenhuma query paralela por engine).

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``db``. Estado mutável de ambiente (MODE, DB_PATH, pool) vive
em ``db.env`` — testes fazem monkeypatch de ``db.env.DB_PATH``.
"""
from __future__ import annotations

from .env import (
    DATABASE_URL,
    DB_PATH,
    MODE,
    _pg_connect,
    _transaction_connection,
)
from .lifecycle import init_db, reset_db
from .migrations import (
    _ensure_execution_events,
    _ensure_job_cols,
    _ensure_league_model_cols,
    _ensure_match_source_cols,
    _ensure_prediction_updated_at,
    _ensure_provenance_cols,
    _ensure_user_cols,
    _record_migration,
)
from .schema import SCHEMA
from .session import _insert_returns_id, get_conn, run_exec, run_query, transaction
from .translate import _PG_SCHEMA, _to_pg_sql

__all__ = [
    "DATABASE_URL",
    "DB_PATH",
    "MODE",
    "SCHEMA",
    "_PG_SCHEMA",
    "_ensure_execution_events",
    "_ensure_job_cols",
    "_ensure_league_model_cols",
    "_ensure_match_source_cols",
    "_ensure_prediction_updated_at",
    "_ensure_provenance_cols",
    "_ensure_user_cols",
    "_insert_returns_id",
    "_pg_connect",
    "_record_migration",
    "_to_pg_sql",
    "_transaction_connection",
    "get_conn",
    "init_db",
    "reset_db",
    "run_exec",
    "run_query",
    "transaction",
]

if MODE == "postgres":
    # Same as the old db module: _pool only exists in PG mode.
    from .env import _pool

    __all__ += ["_pool"]
