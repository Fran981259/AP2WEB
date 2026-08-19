#!/usr/bin/env bash
# Sobe backend (FastAPI) e frontend (Vite) do AP2WEB juntos.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_LOG="$ROOT/backend.log"
FRONTEND_LOG="$ROOT/frontend.log"

# 1. backend
if curl -s -o /dev/null http://127.0.0.1:8000/api/health; then
  echo "[ok] backend já está rodando"
else
  (setsid env PYTHONPATH="$ROOT/backend" "$ROOT/backend/.venv/bin/uvicorn" app.main:app \
     --host 127.0.0.1 --port 8000 >"$BACKEND_LOG" 2>&1 &)
  echo "[ok] backend iniciado em http://127.0.0.1:8000 (log: $BACKEND_LOG)"
fi

# 2. frontend
if curl -s -o /dev/null http://localhost:5173; then
  echo "[ok] frontend já está rodando"
else
  (setsid npm --prefix "$ROOT/frontend" run dev >"$FRONTEND_LOG" 2>&1 &)
  echo "[ok] frontend iniciado em http://localhost:5173 (log: $FRONTEND_LOG)"
fi

echo
echo "Acesse: http://localhost:5173"
echo "(para encerrar: ./stop.sh ou pkill -f uvicorn; pkill -f vite)"
