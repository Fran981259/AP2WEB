# AP2WEB — build de produção (tudo-em-um: FastAPI + frontend compilado).
# Uso:
#   docker build -t ap2web .
#   docker run -p 8000:8000 -e AP2WEB_ORIGINS=https://meudominio.com -e AP2WEB_SECRET=... ap2web
FROM python:3.12-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm install --silent || npm install --no-save --silent

COPY frontend frontend/
RUN cd frontend && npm run build --silent

FROM python:3.12-slim
WORKDIR /app

COPY backend backend/
COPY --from=build /app/frontend/dist frontend/dist

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -q -r backend/requirements.txt

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    AP2WEB_ORIGINS="http://localhost:5173" \
    AP2WEB_SECRET="change-me-in-production"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]