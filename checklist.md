# AP2WEB Delivery Checklist

Last updated: 2026-09-13

Legend: `[x]` verified, `[~]` implemented but not fully verified, `[ ]` pending.

## Core

- [x] FastAPI imports, compiles, lints and typechecks in the configured scope.
- [x] Native FastAPI TestClient lifecycle works; unit/security suite passes.
- [x] Persistent jobs and a standalone worker entrypoint exist.
- [x] Sync, calibration and backtest clients track their active work through the canonical job resource.
- [x] Prediction features use the correct team perspective.
- [x] Poisson/Dixon-Coles numerical invariants have regression tests.
- [~] Bayesian/context/XGBoost paths exist but lack a frozen out-of-sample
  promotion protocol.
- [~] Market/risk calculations work mechanically but do not consume real odds.

## Runtime And Deployment

- [x] Liveness, readiness and dependency endpoints exist.
- [x] Required-worker readiness uses a durable heartbeat; running jobs have renewable leases.
- [x] Compose declares API, worker, frontend, PostgreSQL and Redis separately.
- [x] Compose API, worker, frontend, PostgreSQL and Redis ran healthy on a Docker host on 2026-09-13.
- [x] PostgreSQL/Redis connectivity and durable worker heartbeat were verified in Docker Compose on 2026-09-13.
- [x] SQLite-to-PostgreSQL migration covers operational tables and has local unit coverage.
- [x] SQLite-to-PostgreSQL migration rehearsal passed in Docker Compose on 2026-09-13; source and destination counts matched.
- [x] Post-migration API registration and cookie-session login passed against Compose PostgreSQL/Redis on 2026-09-13.
- [x] PostgreSQL backup and isolated restore passed in Compose on 2026-09-13; application-table counts matched.
- [ ] Railway deploy has API, worker, PostgreSQL and Redis provisioned together.
- [~] Backup and restore were tested in Compose; production monitoring and alerting remain pending.

## Completion Gate

The remaining runtime gates are a SQLite-to-PostgreSQL migration rehearsal and
deployment operational checks. Experimental model paths remain non-promoted
until the protocol in `PROTOCOLO-AVALIACAO-CIENTIFICA.md` passes.
