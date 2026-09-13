# AP2WEB Working Memory

Last updated: 2026-09-13

## Current State

- Test suite: `82 passed`; local lint, typecheck, frontend build, HTTP smoke and data audit pass.
- Primary architecture: FastAPI API, persistent DB jobs, standalone worker,
  React frontend, SQLite local/test and PostgreSQL deployment.
- Production model: Poisson plus canonical Dixon-Coles correction.
- Experimental paths: Bayesian posterior, contextual lambda modifiers, XGBoost
  comparison, market/risk displays. They are not independently validated for
  promotion or profitability.

## Hygiene Audit Completed

- Removed duplicated health-check script, artificial prediction backfill,
  obsolete Render deployment manifest, unused frontend request/loading helpers,
  dead daemon compatibility APIs, and pseudo Bayesian optimisation dependency.
- Replaced feature aggregation with one team-perspective implementation.
- Corrected Dixon-Coles low-score factors and numerical probability safeguards.
- Corrected SQLite write rowcount contract, job repeatability and job recovery
  safety at API startup.
- Corrected scheduled-match selection and post-sync statistic updates.

## Implemented Since Audit

- Durable worker records, heartbeats and renewable job leases; production readiness requires a recent worker heartbeat.
- Case-insensitive username normalization plus a unique database index, with startup failure if legacy duplicates exist.
- Sync, calibration and backtest frontend polling now use `GET /api/jobs/{id}` and durable job progress; backtest status remains read-only for historical metadata.
- Added `PROTOCOLO-AVALIACAO-CIENTIFICA.md`; scientific/market claims remain experimental until its temporal evaluation passes.
- Added opt-in PostgreSQL and Redis connectivity tests (`tests/test_integration_services.py`).
- SQLite-to-PostgreSQL migration now replaces and copies operational state (`workers`, `jobs`, sessions and audit events), with local unit coverage.
- Docker Compose homologation passed on 2026-09-13: API/frontend/PostgreSQL/Redis/worker healthy; direct PostgreSQL and Redis pings succeeded; a recent persisted worker heartbeat was verified.
- SQLite-to-PostgreSQL rehearsal passed in Docker Compose on 2026-09-13: all ten migrated table counts matched (3 users, 68 leagues and zero historical operational rows); worker was recreated and its PostgreSQL heartbeat verified.
- Post-migration HTTP registration and login passed in Compose for `dockercheck2026`, confirming API writes and sessions against PostgreSQL with Redis rate limiting enabled.
- PostgreSQL backup/restore rehearsal passed in Compose on 2026-09-13 via `scripts/verify_pg_backup_restore.sh`; dump `artifacts/ap2web-20260913T221425Z.dump` restored with matching application-table counts.

## Remaining Gates

1. Provision and homologate Railway API, worker, PostgreSQL and Redis services; configure production secrets and monitoring/alerting.
2. Establish a versioned historical snapshot, frozen holdout, calibration curves and confidence intervals before evaluating experimental paths.
3. Supply real bookmaker odds before enabling value-bet or risk recommendations.
4. Remove legacy aggregate status endpoints only after confirming no external consumers depend on them.

## Canonical Documents

- `BASE.md`: architecture and scientific contract.
- `README.md`: local operation.
- `MIGRATION.md`: database migration and backup procedure.
- `RAILWAY.md`: deployment topology.
- `checklist.md`: gates and evidence.
- `LAUDO-HIGIENIZACAO-2026-09-13.md`: full audit report and removals.
