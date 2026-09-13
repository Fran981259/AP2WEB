# AP2WEB Docker Homologation

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
