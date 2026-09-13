# AP2WEB Technical Baseline

## Scientific status

Metrics and market-facing features are experimental until the reproducible protocol in `PROTOCOLO-AVALIACAO-CIENTIFICA.md` passes walk-forward validation and a frozen temporal holdout.

## Purpose

AP2WEB is an authenticated football prediction application. It ingests
Sofascore data, stores it in SQLite locally or PostgreSQL in deployment, and
serves probabilistic 1X2 and score-market estimates.

## Architecture

```text
Sofascore -> persistent database -> canonical features -> Poisson/Dixon-Coles
          -> API -> React client

API requests -> persistent jobs table -> separate worker -> sync/calibration/backtest
```

- API: FastAPI in `backend/app/main.py`.
- Storage: `backend/app/db.py`; SQLite for local/test, PostgreSQL via
  `DATABASE_URL` for deployed environments.
- Worker: `python -m backend.app.worker`; it must be a separate process outside
  local development.
- Frontend: React/Vite in `frontend/`.

## Scientific Contract

- The production baseline is a Poisson score model with canonical Dixon-Coles
  low-score correction in `backend/app/model.py`.
- Team inputs are selected once per match with `goals`, `xg`, or `blend` and
  are then aggregated from the team's perspective in `feature_engine.py`.
- Backtests must use only matches before the evaluated kickoff.
- The standard 1X2 Brier score is multiclass, unnormalised, range `[0, 2]`.
  Comparisons must use the same cohort and the same metric.
- Bayesian, context and XGBoost paths are experimental until a versioned,
  out-of-sample evaluation shows a reproducible benefit against the baseline.
- A positive expected value signal requires externally supplied market odds.
  Synthetic odds derived from model probabilities are not market evidence.

## Non-negotiable Rules

- No code is declared useful solely because it exists or has historical data.
- No model is promoted from in-sample calibration alone.
- No job is recovered merely because an API process starts; leases/heartbeats
  are required before automatic stale-job recovery is introduced.
- No deployment is production-ready without PostgreSQL, Redis for rate limits,
  a worker service, backups, and an integration test of the deployed topology.

## Quality Gate

Run before merging:

```bash
npm run compile
npm run lint
npm run typecheck
npm run lint:frontend
npm run build
npm run test
git diff --check
```

Docker validation is a separate mandatory gate when Docker Engine is available:

```bash
docker compose -f deploy/docker-compose.test.yml up --build
```
