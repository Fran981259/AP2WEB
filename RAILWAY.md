# Railway Deployment

Railway deployment requires four services: API, worker, PostgreSQL and Redis.
The old Render manifest was removed because it could not satisfy the production
Redis and worker requirements.

## Provision

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
AP2WEB_RATE_LIMIT_STORAGE=redis
AP2WEB_REDIS_URL=<Railway Redis URL>
DATABASE_URL=<Railway PostgreSQL URL>
```

## Post-deploy Verification

1. `GET /api/health` returns 200.
2. `GET /api/ready` returns 200.
3. Create an authenticated sync job and confirm the worker completes it.
4. Restart API without losing PostgreSQL data.
5. Verify Redis-backed rate limiting across API replicas if replicas are used.

Do not declare deployment complete until the worker heartbeat/readiness feature
and the Compose integration test described in `checklist.md` are complete.
