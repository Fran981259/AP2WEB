"""DB environment: engine mode, paths, pool and connection factory."""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any


def _read_env_value(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    file_path = (os.environ.get(f"{name}_FILE") or "").strip()
    if value:
        return value
    if not file_path:
        return ""
    with open(file_path, encoding="utf-8") as secret_file:
        return secret_file.read().strip()


def _pool_size(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


DATABASE_URL = _read_env_value("DATABASE_URL")
MODE = "postgres" if DATABASE_URL else "sqlite"

DB_PATH = Path(os.environ.get(
    "AP2WEB_DB_PATH",
    Path(__file__).resolve().parent.parent / "ap2web.db"))

_transaction_connection: ContextVar[Any | None] = ContextVar(
    "transaction_connection", default=None)
if MODE == "postgres":
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    _pool_min_size = _pool_size("AP2WEB_DB_POOL_MIN_SIZE", 1, 1, 10)
    _pool_max_size = _pool_size("AP2WEB_DB_POOL_MAX_SIZE", 3, _pool_min_size, 20)
    _pool = ConnectionPool(
        DATABASE_URL,
        min_size=_pool_min_size,
        max_size=_pool_max_size,
        timeout=5,
        max_idle=60,
        max_lifetime=300,
        check=ConnectionPool.check_connection,
        kwargs={"row_factory": dict_row},
    )
def _pg_connect():
    """Retorna conexão do pool (context manager compatível)."""
    return _pool.connection()
