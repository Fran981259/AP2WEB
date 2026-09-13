#!/usr/bin/env bash
set -euo pipefail

# Creates a compressed PostgreSQL backup, restores it to an isolated database,
# and verifies that the application tables have identical row counts.
COMPOSE=(docker compose -f deploy/docker-compose.test.yml)
RESTORE_DB="ap2web_restore_check"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="artifacts"
BACKUP_FILE="${BACKUP_DIR}/ap2web-${STAMP}.dump"
CONTAINER_DUMP="/tmp/ap2web-${STAMP}.dump"

mkdir -p "$BACKUP_DIR"
umask 077

cleanup() {
  "${COMPOSE[@]}" exec -T postgres rm -f "$CONTAINER_DUMP" >/dev/null 2>&1 || true
  "${COMPOSE[@]}" exec -T postgres dropdb -U ap2web --if-exists "$RESTORE_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${COMPOSE[@]}" ps --status running postgres | grep -q postgres || {
  printf '%s\n' 'PostgreSQL Compose service is not running.' >&2
  exit 1
}

"${COMPOSE[@]}" exec -T postgres pg_dump -U ap2web -d ap2web -Fc > "$BACKUP_FILE"
"${COMPOSE[@]}" cp "$BACKUP_FILE" "postgres:${CONTAINER_DUMP}"
"${COMPOSE[@]}" exec -T postgres sh -ceu \
  "dropdb -U ap2web --if-exists '$RESTORE_DB'; createdb -U ap2web '$RESTORE_DB'; pg_restore -U ap2web --exit-on-error -d '$RESTORE_DB' '$CONTAINER_DUMP'"

counts_sql="SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'leagues', COUNT(*) FROM leagues UNION ALL SELECT 'teams', COUNT(*) FROM teams UNION ALL SELECT 'matches', COUNT(*) FROM matches UNION ALL SELECT 'predictions', COUNT(*) FROM predictions UNION ALL SELECT 'league_models', COUNT(*) FROM league_models UNION ALL SELECT 'workers', COUNT(*) FROM workers UNION ALL SELECT 'jobs', COUNT(*) FROM jobs UNION ALL SELECT 'auth_sessions', COUNT(*) FROM auth_sessions UNION ALL SELECT 'audit_events', COUNT(*) FROM audit_events ORDER BY 1"
source_counts="$("${COMPOSE[@]}" exec -T postgres psql -U ap2web -d ap2web -At -c "$counts_sql")"
restored_counts="$("${COMPOSE[@]}" exec -T postgres psql -U ap2web -d "$RESTORE_DB" -At -c "$counts_sql")"

if [[ "$source_counts" != "$restored_counts" ]]; then
  printf '%s\n' 'Backup/restore row counts differ.' >&2
  diff -u <(printf '%s\n' "$source_counts") <(printf '%s\n' "$restored_counts") || true
  exit 1
fi

printf 'backup=%s\nrestore=%s\nstatus=ok\n' "$BACKUP_FILE" "$RESTORE_DB"
