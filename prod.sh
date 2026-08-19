#!/usr/bin/env bash
# AP2WEB — produção tudo-em-um (FastAPI serve API + frontend compilado).
# Uso:
#   AP2WEB_ORIGINS=https://meudominio.com ./prod.sh            # roda na porta 8000
#   AP2WEB_ORIGINS=... PORT=8080 ./prod.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"

# carrega .env se existir (AP2WEB_ORIGINS, AP2WEB_SECRET, PORT)
if [ -f "$ROOT/.env" ]; then
  set -a; . "$ROOT/.env"; set +a
fi

# 1. compila o frontend (instala deps só se necessário)
echo "[1/3] Compilando frontend..."
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  (cd "$ROOT/frontend" && npm install --silent)
fi
(cd "$ROOT/frontend" && npm run build --silent)

# 2. (re)start do backend
if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/health" 2>/dev/null; then
  echo "[2/3] Backend já rodando na porta $PORT"
else
  echo "[2/3] Iniciando backend na porta $PORT..."
  (setsid env PYTHONPATH="$ROOT/backend" \
     AP2WEB_ORIGINS="${AP2WEB_ORIGINS:-}" \
     AP2WEB_SECRET="${AP2WEB_SECRET:-}" \
     "$ROOT/backend/.venv/bin/uvicorn" app.main:app \
     --host 0.0.0.0 --port "$PORT" >"$ROOT/prod.log" 2>&1 &)
  sleep 2
fi

echo "[3/3] Testando..."
curl -s "http://127.0.0.1:$PORT/api/health" && echo
echo
echo "API + frontend: http://<seu-ip-ou-dominio>:$PORT"
echo "CORS liberado para: ${AP2WEB_ORIGINS:-<default localhost>}"
echo "(log: $ROOT/prod.log — encerrar com: pkill -f 'uvicorn app.main')"