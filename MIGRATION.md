# Database Migration And Recovery

## Supported Modes

| Environment | Database |
|---|---|
| Local and test | SQLite via `AP2WEB_DB_PATH` |
| Deployment | PostgreSQL via `DATABASE_URL` |

`backend/app/db.py` supports both modes. Test PostgreSQL separately before cutover; SQLite
success is not PostgreSQL validation.

## SQLite To PostgreSQL Cutover

1. Stop API writes and worker jobs.
2. Back up SQLite with `sqlite3 backend/ap2web.db ".backup 'backup.db'"`.
3. Set `DATABASE_URL`.
4. Run `backend/.venv/bin/python backend/scripts/migrate_sqlite_to_pg.py`.
   When running from a container, copy the source database into that container
   and set `AP2WEB_SQLITE_SOURCE_PATH=/path/to/source.db`.
5. The migrator truncates and copies `users`, data tables, `workers`, `jobs`,
   `auth_sessions` and `audit_events`. Compare source and destination counts
   for each table; absent operational tables in an older SQLite source are
   treated as empty. It intentionally does not copy `schema_migrations`.
6. Start API and worker against PostgreSQL and execute an end-to-end job.

## Backup And Restore

```bash
pg_dump "$DATABASE_URL" -Fc -f ap2web.dump
pg_restore -d "$DATABASE_URL" ap2web.dump
```

For the isolated Compose rehearsal, run `bash scripts/verify_pg_backup_restore.sh`.
It leaves a compressed dump in `artifacts/`, restores it to a temporary database,
compares application-table counts, and removes the temporary database.

Backups, offsite replication, retention and restore testing are release gates,
not documentation-only tasks.
