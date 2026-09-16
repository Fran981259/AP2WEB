FROM python:3.12-slim AS backend

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY --from=backend /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin

COPY --from=frontend-build /app/frontend/dist ./frontend/dist/

COPY backend/ ./backend/

RUN mkdir -p /data

ENV AP2WEB_DB_PATH=/data/ap2web.db
ENV AP2WEB_ORIGINS=https://app.theprostatereview.com

EXPOSE 8000

# Container liveness must not depend on another service. `/api/ready` remains
# the strict dependency/readiness endpoint, but using it as the Docker check
# made an API replica unhealthy while the worker restarted during a rollout.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; port=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://localhost:{port}/api/health', timeout=4).read()" || exit 1

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
