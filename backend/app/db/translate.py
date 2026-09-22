"""SQLite-dialect translation helpers (runtime + schema)."""
from __future__ import annotations

import re

from .schema import SCHEMA


def _to_pg_sql(sql: str) -> str:
    """Traduz dialeto SQLite para Postgres.

    - placeholders ? -> %s
    - date(expr)     -> (expr)::date        (evita 'match_date' via \b)
    - date(?)        -> (left(?,10))::date  (PG é estrito com formato de data)
    - datetime('now')-> to_char(now(),...)
    - window         -> "window"            (palavra reservada no PG)
    """
    # 1) params dentro de date(): trunca para YYYY-MM-DD antes do cast
    s = re.sub(r"\bdate\(\s*\?\s*\)", "(left(?,10))::date", s := sql)
    # 2) placeholders ? -> %s
    s = s.replace("?", "%s")
    # 3) colunas: date(expr) -> (expr)::date
    s = re.sub(r"\bdate\(([^()]+)\)", r"(\1)::date", s)
    # 4) datetime('now')
    s = s.replace("datetime('now')",
                  "to_char(now(), 'YYYY-MM-DD HH24:MI:SS')")
    # 5) palavra reservada
    s = re.sub(r'\bwindow\b', '"window"', s)
    return s
_PG_SCHEMA = re.sub(
    r"\bdate\(([^()]+)\)", r"(\1)::date",
    SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT",
                   "SERIAL PRIMARY KEY")
          .replace("datetime('now')",
                   "to_char(now(), 'YYYY-MM-DD HH24:MI:SS')")
          .replace(" window INTEGER", ' "window" INTEGER'))
