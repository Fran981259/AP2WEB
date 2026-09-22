# AP2WEB Project Map

## Runtime topology
```
Sofascore → db (SQLite/PG) → features → Poisson/Dixon-Coles → FastAPI → React
API → jobs table → worker process (sync/calibrate/backtest)
Swarm: app, worker, postgres, redis, caddy (deploy/docker-stack.yml)
```

## Backend modules (`backend/app/`)
| Module | Role |
|--------|------|
| `main.py` | FastAPI composition root (lifespan, handlers, CORS, SPA) |
| `api/` | Routers split from `main.py` (auth, sync, jobs, data, prediction, learning, market, risk, evolution, backtest, admin, health) |
| `api/v1.py` | `/api/v1/*` aliases with `{data, message, statusCode}` envelope (legacy `/api/*` unchanged) |
| `config.py` | Settings + fail-fast production validation (`*_FILE` secrets) |
| `db/` | Dual engine SQLite/PostgreSQL: `env`, `translate`, `schema`, `session`, `migrations`, `lifecycle` |
| `auth/` / `security/` | JWT, PBKDF2, sessions, CSRF, audit, safe errors (`core`, `password`/`csrf`, `users`/`tokens`/`sessions`/`audit`/`errors`, `dependencies`) |
| `ratelimit.py` | Named limits (memory/redis) |
| `jobs/` | Persistent jobs + standalone worker (`registry`, `workers`, `runner`, `loop`) |
| `prediction/` | Match prediction, Poisson/Dixon-Coles (`settings`, `context`, `history`, `bayesian`, `builder`, `service`) |
| `feature_engine.py` | Team-perspective features |
| `learning/` | Calibration + walk-forward backtest (`grids`, `walkforward`, `calibration`) |
| `backtest/` | Temporal CV, MetaLearner, cycle loop (`paths`, `executions`, `temporal`, `meta`, `state`, `cycle`, `detailed`, `loop`) |
| `sofascore/` | Source ingestion (`tables`, `client`, `seasons`, `upserts`, `sync`, `queries`) |
| `market.py` / `risk/` / `odds_store.py` | EV, Kelly, 1X2 quotes (`risk/`: `policy`, `match`, `portfolio`) |
| `scientific/` / `evolution/` | Eval protocol (`records`, `baselines`, `metrics`, `snapshot`, `protocol`) + metrics drift (`paths`, `executions`, `measure`, `history`, `analysis`, `cli`) |

GOLDCODE file rule: every module above is ≤300 lines; the former
`backtest_engine.py`, `db.py`, `prediction.py`, `auth.py`,
`sofascore_data.py`, `learning.py`, `jobs.py`, `scientific_protocol.py`,
`security.py`, `risk.py`, `evolution_tracker.py` live on as same-named
packages re-exporting the identical public API.

## Frontend (`frontend/src/`)
- `App.jsx` — session shell, AuthScreen, Dashboard (monolith → extract under `components/` + `features/`)
- `api.js` — fetch client (cookies + CSRF)
- `styles.css` — tokens + theme
- `hooks/usePolling.js`

## Mobile (`mobile/`)
- `App.tsx` — Expo login screen
- `src/api.ts` — bearer login, refresh and logout client
- `src/storage.ts` — SecureStore session persistence
- `src/theme.ts` — mobile design tokens

## Deploy (`deploy/`)
- `docker-stack.yml` production; `docker-compose.test.yml` local validation only
- Secrets: external Swarm `ap2web_secret_*`, `ap2web_database_url_*`, `ap2web_postgres_password_*`

## Docs
- `BASE.md` scientific/architecture contract
- `MIGRATION.md` SQLite→PG + backup/restore
- `deploy/README.md` rollout checklist
- `checklist.md` delivery checklist
