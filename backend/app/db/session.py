"""Per-call database sessions: connections, transactions, query/exec."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager

from . import env
from .env import _pg_connect
from .translate import _to_pg_sql

if env.MODE == "postgres":
    import psycopg  # error-path handling in _pg_exec (PG mode only)


def get_conn() -> sqlite3.Connection:
    """SQLite apenas. Em modo Postgres, use run_query/run_exec."""
    conn = sqlite3.connect(env.DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn
@contextmanager
def transaction():
    """Run database calls in one transaction on either supported engine."""
    if env._transaction_connection.get() is not None:
        yield
        return
    if env.MODE == "sqlite":
        conn = get_conn()
        token = env._transaction_connection.set(conn)
        try:
            conn.execute("BEGIN")
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            env._transaction_connection.reset(token)
            conn.close()
        return
    with _pg_connect() as conn:
        token = env._transaction_connection.set(conn)
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            env._transaction_connection.reset(token)
def run_query(query: str, params: tuple = ()) -> list[dict]:
    """SELECT — retorna linhas acessíveis por r["coluna"]."""
    conn = env._transaction_connection.get()
    if conn is not None:
        if env.MODE == "sqlite":
            return conn.execute(query, params).fetchall()
        return conn.execute(_to_pg_sql(query), params).fetchall()
    if env.MODE == "sqlite":
        conn = get_conn()
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()
    with _pg_connect() as conn:
        return conn.execute(_to_pg_sql(query), params).fetchall()
def run_exec(query: str, params: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE — retorna id (INSERT) ou rowcount (UPDATE/DELETE).

    Em Postgres, INSERTs em tabelas com chave numérica ``id`` ganham RETURNING
    id para preservar o contrato lastrowid usado pelo restante do código.
    """
    conn = env._transaction_connection.get()
    if conn is not None:
        if env.MODE == "sqlite":
            cur = conn.execute(query, params)
            if query.lstrip().upper().startswith("INSERT"):
                return cur.lastrowid if cur.lastrowid is not None else 0
            return cur.rowcount
        q = _to_pg_sql(query)
        returns_id = _insert_returns_id(q)
        if returns_id:
            q += " RETURNING id"
        return _pg_exec(conn, q, params, returns_id, commit=False)
    if env.MODE == "sqlite":
        conn = get_conn()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            if query.lstrip().upper().startswith("INSERT"):
                return cur.lastrowid if cur.lastrowid is not None else 0
            return cur.rowcount
        finally:
            conn.close()
    q = _to_pg_sql(query)
    returns_id = _insert_returns_id(q)
    if returns_id:
        q += " RETURNING id"
    with _pg_connect() as conn:
        return _pg_exec(conn, q, params, returns_id)


def _insert_returns_id(query: str) -> bool:
    """Only tables with an integer ``id`` may use PostgreSQL RETURNING id."""
    match = re.match(r'\s*INSERT(?:\s+OR\s+\w+)?\s+INTO\s+"?([a-z_]+)', query, re.I)
    return bool(match and "RETURNING" not in query.upper() and match.group(1).lower() in {
        "users", "leagues", "teams", "matches", "predictions", "jobs",
        "auth_sessions", "audit_events",
        "execution_events",
    })
def _pg_exec(conn, q: str, params: tuple, returns_id: bool, commit: bool = True) -> int:
    """Executa com RETURNING id; se a tabela não tiver coluna id, cai para rowcount."""
    try:
        cur = conn.execute(q, params)
        row = cur.fetchone() if returns_id else None
        if commit:
            conn.commit()
        return row["id"] if row else cur.rowcount
    except psycopg.errors.UndefinedColumn:
        conn.rollback()
        if not returns_id:
            raise
        cur = conn.execute(q.replace(" RETURNING id", ""), params)
        if commit:
            conn.commit()
        return cur.rowcount
