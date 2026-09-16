# AP2WEB Docker Homologation

## Docker Swarm / Portainer

Use `docker-stack.yml` as the single source of truth for the production stack.
The image is built and published to `ghcr.io/fran981259/ap2web:latest` by the
`Publish container image` GitHub Actions workflow.

In Portainer, deploy the stack from this file and define these variables in the
stack environment (never commit their values):

- `AP2WEB_SECRET`: a random value with at least 32 characters.
- `POSTGRES_PASSWORD`: a unique database password.
- `AP2WEB_ORIGINS`: the exact public application origin, for example
  `https://app.example.com`.

To create the first administrator without running database SQL, define both
`AP2WEB_BOOTSTRAP_ADMIN_USERNAME` and `AP2WEB_BOOTSTRAP_ADMIN_PASSWORD` for
the first deployment. The application uses them only when no active admin
exists; remove both variables after the account is created.

Production requires HTTPS and these values:

```text
AP2WEB_ENV=production
AP2WEB_COOKIE_SECURE=true
```

For a Tailnet-only HTTP smoke test, use `AP2WEB_ENV=development` and
`AP2WEB_COOKIE_SECURE=false`. Do not leave that configuration in production.

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
