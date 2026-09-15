# Railway Deployment

Railway deployment requires four services: API, worker, PostgreSQL and Redis.
The old Render manifest was removed because it could not satisfy the production
Redis and worker requirements.

## Current Production Status

The Railway API, standalone worker, PostgreSQL, Redis, public readiness, and
UptimeRobot monitors were verified on 2026-09-13. This is operational evidence,
not scientific model validation.

## Provision / Recovery

1. Create PostgreSQL and Redis services.
2. Create API service from this repository using `railway.json` / `Dockerfile`.
3. Create a second service from the same repository with command:

```bash
python -m backend.app.worker
```

4. Configure both API and worker with the same `DATABASE_URL` and production
settings. The worker does not need an HTTP health check.

## Required API Variables

```text
AP2WEB_ENV=production
AP2WEB_SECRET=<random value, at least 32 characters>
AP2WEB_ORIGINS=https://<frontend-domain>
AP2WEB_COOKIE_SECURE=true
AP2WEB_ENFORCE_ROLES=true
AP2WEB_REQUIRE_WORKER=true
AP2WEB_RATE_LIMIT_STORAGE=redis
AP2WEB_REDIS_URL=${{Redis.REDIS_URL}}
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

## Post-deploy Verification

1. `GET /api/health` returns 200.
2. `GET /api/ready` returns 200.
3. Create an authenticated sync job and confirm the worker completes it.
4. Restart API without losing PostgreSQL data.
5. Verify Redis-backed rate limiting across API replicas if replicas are used.

## Operations

Use `GET /api/health` for liveness and `GET /api/ready` for dependency and
worker readiness. UptimeRobot monitors both endpoints every five minutes with
e-mail alerts. PostgreSQL must remain private except for a short, credential-
rotated migration window. See `MIGRATION.md` for backup and restore procedures.

Railway currently accepts `railway.json`, but its Config as Code format is
deprecated; migrate to `.railway/railway.ts` before 2026-12-01.
