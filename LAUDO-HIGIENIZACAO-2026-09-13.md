# AP2WEB Deep Technical And Scientific Hygiene Report

Date: 2026-09-13

## Scope And Method

This audit used static inventory, AST duplicate detection, import/use tracing,
database read-only integrity checks, dependency checks, deterministic numerical
counterexamples, unit/security tests, lint, typechecking and frontend build.

Static findings were treated as candidates, not deletion proof. A file was
removed only when it had no production consumer or was an obsolete duplicate.
The audit did not use network data, Docker Engine, PostgreSQL or Redis; claims
about those environments remain unverified.

## Executive Verdict

The repository was viable but not scientifically or operationally ready for
production. The primary risk was not file count: it was disagreement between
the stated model and the implemented calculations. The cleanup removed proven
residue, repaired core numerical/data-flow defects, and replaces fragmented
documents with a smaller canonical set. Experimental model and betting layers
remain non-promotable pending formal evaluation.

## Verified Findings And Repairs

### F1 - Critical: non-canonical Dixon-Coles implementation

- Evidence: `backend/app/model.py` used factors different from Dixon and Coles
  (1997), and accepted parameters producing negative probability cells.
- Repair: canonical low-score factors were implemented; rho is projected to a
  match-specific admissible interval before matrix construction.
- Verification: `tests/test_scientific_core.py` tests all four canonical cells,
  non-negativity and normalisation.
- Consequence: historic calibration values and stored metrics are not
  comparable to the repaired model. Recalibration and a fresh frozen evaluation
  are mandatory before publication of new claims.

### F2 - Critical: feature orientation and blend drift

- Evidence: away-team prediction statistics used home-oriented xG, goals mode
  could collapse to zero, and blend was applied twice. Missing xG became zero
  rather than falling back to observed goals.
- Repair: `feature_engine.py` is now the canonical selection and team
  perspective layer; prediction and experiment scripts use it.
- Verification: deterministic tests cover home/away, `goals`, `xg`, `blend`,
  and missing xG.
- Consequence: all prior calibration, Bayesian/context promotion and XGBoost
  comparison outputs are invalidated as scientific evidence.

### F3 - Critical: production-health metric contamination

- Evidence: an artificial backfill created predictions after matches had
  happened and the health check compared binary pick Brier with multiclass
  Brier, using unverified payload reconstruction.
- Repair: removed `scripts/backfill_predictions.py`; consolidated the two
  health-check copies into `backend/app/model_health_check.py`. The replacement
  only includes records with timestamps strictly before kickoff, deduplicates
  per match/version, rescoring full 1X2 vectors on matched cohorts.
- Limitation: timestamps and payloads are not immutable provenance. The result
  is descriptive, not a certification of generalisation, calibration or profit.

### F4 - High: job lifecycle could create false execution state

- Evidence: startup automatically marked every running job failed although a
  separate worker may still be live; SQLite writes returned `lastrowid` for
  updates, breaking optimistic claim semantics; completed jobs could not rerun.
- Repair: write helpers return update rowcounts, completion/failure/cancellation
  release idempotency keys, status transitions are guarded, and startup no
  longer recovers live jobs. Recovery is explicitly administrative until leases
  and heartbeats exist.
- Verification: job tests cover repetition, cancellation race and startup.

### F5 - High: scheduled flow and delayed statistics were broken

- Evidence: prediction selection did not filter scheduled matches correctly;
  market queried a nonexistent `fixture` status; the post-sync statistics path
  constructed invalid SQL and nested parameters.
- Repair: upcoming/market paths use `scheduled`; post-sync uses parameterised
  direct updates.
- Verification: scheduled-prediction regression test added.

### F6 - Medium: frontend had unused abstractions and overlapping timers

- Evidence: `useApiRequest` and loading-state components had no imports;
  `App.jsx` maintained three independent `setInterval` flows despite a separate
  unused polling hook.
- Repair: removed unused files and replaced the polling hook with sequential,
  abortable `setTimeout` polling; Dashboard uses it for sync, calibration and
  backtest status.
- Limitation: Dashboard remains a 2,000-line monolith. It is now safer but must
  be split by domain after the job API contract is final.

### F7 - Medium: obsolete deployment and dependency residue

- Removed `render.yaml`: incompatible with the defined Redis + worker topology.
- Removed pseudo `scikit-optimize` usage: its objective only searched recorded
  points rather than evaluating candidates, so it was not Bayesian optimisation.
- Removed dead daemon compatibility functions and their tests.
- Removed duplicated model health script.

## Removed Or Replaced Files

| Path | Action | Reason |
|---|---|---|
| `render.yaml` | removed | unsupported production topology |
| `scripts/model_health_check.py` | removed | duplicate of app module |
| `scripts/backfill_predictions.py` | removed | post-outcome data contamination |
| `frontend/src/hooks/useApiRequest.js` | removed | no imports |
| `frontend/src/components/LoadingState.jsx` | removed | no imports |
| `technical_audit.txt` | removed | stale pre-hardening claims |
| `REPORT-MANUTENCAO-18-SECOES.md` | removed | obsolete session narrative |
| `BASE.md`, `README.md`, `MEMORY.md`, `checklist.md`, `RAILWAY.md`, `MIGRATION.md` | replaced | conflicting historical documentation consolidated |

## Remaining Blocking Risks

1. No frozen temporal holdout, confidence intervals, calibration curve or
   promotion protocol exists for Bayesian/context/XGBoost paths.
2. Risk/value features do not use observed bookmaker odds. Their synthetic odds
   cannot establish an edge or profitability.
3. Worker readiness lacks heartbeat and lease semantics.
4. PostgreSQL and Redis have no executed integration test in this environment.
5. The migration script omits operational tables and is unsafe for a full
   production cutover until extended and tested.
6. Username uniqueness is case-insensitive in application code but not enforced
   by a database-normalised unique constraint.
7. API orchestration remains concentrated in `main.py`; frontend orchestration
   remains concentrated in `App.jsx`.

## Evidence Executed

- `backend/.venv/bin/python scripts/audit_structure.py`: 390 non-ignored files
  at scan time; found duplicated health-check bodies and unused frontend files.
- `backend/.venv/bin/python scripts/audit_data.py backend/ap2web.db`: integrity
  `ok`, zero foreign-key violations; the tracked local database has schema and
  seeded leagues but no matches/models/predictions.
- `backend/.venv/bin/pip check`: no broken Python requirements.
- `npm run test`: `81 passed` after repairs.
- `npm run lint`, `npm run typecheck`, `npm run lint:frontend` and `npm run
  build`: passed after the final cleanup.
- `backend/.venv/bin/python tests/runtime_http_suite.py`: health, readiness and
  security headers passed against a real temporary Uvicorn process.
- Production dependency audits: `npm audit --omit=dev` and frontend equivalent
  found zero vulnerabilities; `pip check` found no broken requirements.

## Completion Roadmap

1. Implement worker heartbeats and job leases; test API/worker as separate
   processes.
2. Formalise a versioned data snapshot plus train/validation/test temporal split.
   Recalibrate Poisson, then re-evaluate every experimental path on the holdout.
3. Hide or label experimental and synthetic-odds controls until step 2 and real
   odds ingestion are complete.
4. Add PostgreSQL/Redis CI integration and execute Compose validation.
5. Extend/test migration for every operational table, backups and restoration.
6. Split `App.jsx` and `main.py` only after their contracts are covered by tests.
