# AP2WEB

AP2WEB ingests football match data from Sofascore and exposes authenticated
probabilistic predictions. The production baseline is a Poisson score model
with a canonical Dixon-Coles low-score correction.

Read `BASE.md` for technical and scientific rules. Read
`LAUDO-HIGIENIZACAO-2026-09-13.md` before changing the model or deployment.

## Local Development

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
npm ci --prefix frontend

export AP2WEB_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
npm run dev
```

Run the worker separately when testing jobs:

```bash
npm run worker
```

SQLite is the default local database. Never use it as the deployed database.

## Quality Gate

```bash
npm run compile
npm run lint
npm run typecheck
npm run lint:frontend
npm run build
npm run test
```

## Health Endpoints

- `GET /api/health`: process liveness.
- `GET /api/ready`: API/database/schema readiness and recent durable worker
  heartbeat when a worker is required.
- `GET /api/health/dependencies`: safe dependency status.

## Deployment

Railway is the production target. API, standalone worker, PostgreSQL, Redis,
and UptimeRobot readiness/liveness monitors were validated on 2026-09-13.
Scientific features and market/risk signals remain experimental. See
`RAILWAY.md`, `MIGRATION.md`, and `PROTOCOLO-AVALIACAO-CIENTIFICA.md`.
