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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TABLES = ["users", "leagues", "teams", "matches", "predictions", "league_models"]


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        sys.exit("Defina DATABASE_URL apontando para o Postgres de destino.")
    os.environ.pop("AP2WEB_DB_PATH", None)

    from app import db
    if db.MODE != "postgres":
        sys.exit("DATABASE_URL não reconhecida — modo ativo: " + db.MODE)

    import psycopg.rows  # noqa: F401 (garante registro do dict_row)
    src = db.get_conn()
    src.row_factory = __import__("sqlite3").Row

    db.init_db()  # cria schema no destino
    with db._pg_connect() as dst:
        for table in TABLES:
            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                print(f"{table}: 0 linhas")
                continue
            cols = list(rows[0].keys())
            dst.execute(f'DELETE FROM "{table}"')
            placeholders = ",".join("%s" for _ in cols)
            collist = ",".join(f'"{c}"' for c in cols)
            sql = f'INSERT INTO "{table}"({collist}) VALUES({placeholders})'
            for r in rows:
                dst.execute(sql, tuple(r[c] for c in cols))
            # resequencia as sequences após ids explícitos
            pk = {"league_models": "league_id"}.get(table, "id")
            if pk == "id":
                dst.execute(
                    f'SELECT setval(pg_get_serial_sequence(\'{table}\',\'id\'), '
                    f'COALESCE((SELECT MAX(id) FROM "{table}"), 1))')
            print(f"{table}: {len(rows)} linhas migradas")
    print("\n✅ Migração concluída.")


if __name__ == "__main__":
    main()
