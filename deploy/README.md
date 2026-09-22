# AP2WEB Deployment

## Docker Swarm Production

`docker-stack.yml` is the production source of truth. It deploys one API,
one worker, PostgreSQL, Redis, and Caddy. Only Caddy publishes ports 80 and
443; API, database, and Redis remain on the private overlay network.

Before a production deploy:

1. Configure public DNS for `AP2WEB_PUBLIC_DOMAIN` to this host and allow
   inbound TCP 80/443 so Caddy can obtain a certificate.
2. Copy `deploy/.env.production.example` to an untracked location and set a
   public domain plus an immutable CI image tag.
3. Create the external Swarm secrets. Do not pass these values through stack
   environment variables or commit them to a file:

```bash
printf '%s' '<random-AP2WEB-secret>' | docker secret create ap2web_secret_v1 -
printf '%s' '<postgres-password>' | docker secret create ap2web_postgres_password_v1 -
printf '%s' 'postgresql://ap2web:<postgres-password>@postgres:5432/ap2web' \
  | docker secret create ap2web_database_url_v1 -
```

4. Render before applying:

```bash
set -a
. /path/to/ap2web-production.env
set +a
docker stack config -c deploy/docker-stack.yml
```

5. Deploy and verify:

```bash
docker stack deploy -c deploy/docker-stack.yml ap2web
curl --fail --silent --show-error "https://${AP2WEB_PUBLIC_DOMAIN}/api/health"
curl --fail --silent --show-error "https://${AP2WEB_PUBLIC_DOMAIN}/api/ready"
```

The secret values cannot be changed in place. Rotate by creating versioned
secret names, changing the corresponding names in the untracked environment
file, deploying, verifying readiness, then removing the old secrets. Back up
PostgreSQL before rotating the database password.

`app_data` persists backtest and evolution artifacts outside the application
container. Before the first production deployment, decide whether existing
artifacts need to be copied into this volume; do not overwrite a validated
baseline without a reproducible backup.

## Rollout Checklist

Run in order. Stop at the first failure.

1. **Backup**: `pg_dump -Fc` from the current PostgreSQL, copied off-host, and
   restore-tested into an isolated database. Record row counts.
2. **Rotate exposed secrets**: create `*_v2` Swarm secrets for AP2WEB,
   PostgreSQL password and database URL. Keep the old ones until step 7.
3. **Set environment**: untracked file with `AP2WEB_PUBLIC_DOMAIN`,
   `AP2WEB_IMAGE` (immutable SHA) and the three `*_SECRET_NAME` values.
4. **DNS + firewall**: public DNS points at this host; only TCP 22/80/443
   reachable; 8000/5432/6379 not reachable from the Internet.
5. **Render**: `docker stack config -c deploy/docker-stack.yml` must succeed.
6. **Deploy**: `docker stack deploy -c deploy/docker-stack.yml ap2web`.
   Verify `/api/health` and `/api/ready` over HTTPS, then confirm the SPA
   loads and a job round-trips through the worker.
7. **Cleanup**: remove old secrets and the previous stack definition only
   after a full observation window.

## Rollback

1. Stop writes: scale API and worker to 0 replicas.
2. Restore the step-1 dump into a fresh database if the schema changed.
3. Redeploy the previous known-good image tag by changing `AP2WEB_IMAGE` and
   running `docker stack deploy` again; Swarm's `rollback_config` restores the
   previous task spec automatically on a failed update.
4. Confirm `/api/ready` returns 200 before restoring traffic.

Volumes (`ap2web_postgres_data`, `ap2web_redis_data`, `app_data`) are never
removed by a rollback. Never run `docker volume rm` or `down -v` during a
production rollback.

The `worker` service deliberately overrides the API image healthcheck. The API
image checks its own liveness at `/api/health`; a standalone worker does not
serve HTTP and therefore needs a durable worker-heartbeat check instead.

`/api/ready` is intentionally stricter than the container healthcheck: it also
requires the database schema and, in production, a live worker heartbeat.

This compose file is isolated from production and runs API, worker, frontend,
PostgreSQL and Redis together:

```bash
docker compose -f deploy/docker-compose.test.yml up --build
```

Validation endpoints:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/ready
curl http://127.0.0.1:5173/api/health
```

Stop and remove test data:

```bash
docker compose -f deploy/docker-compose.test.yml down -v
```

This environment uses test credentials and must not be exposed to the Internet.
