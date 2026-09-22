# AP2WEB — Agent Rules

Stack: FastAPI + React/Vite + PostgreSQL/SQLite + Redis rate-limit + Docker Swarm.

## Layout
- `backend/app/` — API (`main.py`), domain modules, `db.py` dual-engine.
- `frontend/src/` — SPA (`App.jsx` entry composition, `api.js` HTTP client).
- `deploy/` — Swarm production stack (`docker-stack.yml` is source of truth).
- `tests/` — pytest suite (`npm run test`).

## Quality gate (run before commit)
```
npm run lint && npm run typecheck && npm run lint:frontend && npm run test && npm run build
```

## Non-negotiable
- No secrets in code, logs, or git (use `*_FILE` / Swarm secrets).
- Production requires PostgreSQL, Redis rate-limit, separate worker.
- CSRF + rate_limit on every mutating endpoint.
- Files ≤300 lines; functions ≤20 lines; ≤3 parameters when practical.
- Design tokens only in `frontend/src/styles.css` (`:root`); no new raw hex outside tokens; no box-shadow/gradient (GOLDCODE 5.2).
- API paths under `/api/`; new/changed routes go under `/api/v1/` with envelope `{data, message, statusCode}` while keeping legacy `{ok, ...}` for existing clients.

## GOLDCODE
See `skill/regras globais agente.md` (global_rules.md v3.0).
