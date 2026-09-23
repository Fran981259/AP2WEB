#!/usr/bin/env bash
# AP2WEB — Local development launcher (Phase 3)
# Starts FastAPI backend (127.0.0.1:8000) and Vite frontend (localhost:5173).
#
# Paths touched by this script (nothing else):
#   • only the child processes it spawns (backend + frontend)
#   • systemd services are NEVER stopped/masked unless AP2WEB_MANAGE_SYSTEMD=true
#
# Usage: npm run dev   (or directly: bash scripts/dev.sh)
set -Euo pipefail

# ── Resolve repository root from script location ─────────────────────────────
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$( cd -- "${SCRIPT_DIR}/.." &> /dev/null && pwd )"
cd "${REPO_ROOT}"

# ── Optional .env (gitignored; fills only vars not already exported) ─────────
# Priority: shell exports > .env > defaults abaixo.
if [[ -f "${REPO_ROOT}/.env" ]]; then
  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ "${line}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || continue
    key="${line%%=*}"
    val="${line#*=}"
    val="${val%\"}"
    val="${val#\"}"
    [[ -v "${key}" ]] || export "${key}=${val}"
  done < "${REPO_ROOT}/.env"
  echo "[dev.sh] .env carregado: ${REPO_ROOT}/.env"
fi

# ── Local-development defaults (do not overwrite if user already set them) ────
: "${AP2WEB_ENV:=development}"
: "${AP2WEB_SECRET:=dev-secret-change-me-please-use-env-var-0123456789abcdef}"
: "${AP2WEB_DB_PATH:=/tmp/ap2web-dev.db}"
: "${AP2WEB_ORIGINS:=http://localhost:5173,http://127.0.0.1:5173}"
: "${AP2WEB_ENFORCE_ROLES:=false}"
: "${AP2WEB_ENABLE_WORKER:=false}"
: "${AP2WEB_MANAGE_SYSTEMD:=false}"
: "${PORT:=8000}"
: "${FRONTEND_PORT:=5173}"

export AP2WEB_ENV AP2WEB_SECRET AP2WEB_DB_PATH AP2WEB_ORIGINS \
       AP2WEB_ENFORCE_ROLES AP2WEB_ENABLE_WORKER PORT

# ── Preflight checks ─────────────────────────────────────────────────────────
VENV_UVICORN="${REPO_ROOT}/backend/.venv/bin/uvicorn"
if [[ ! -x "${VENV_UVICORN}" ]]; then
  echo "[dev.sh] ERRO: ${VENV_UVICORN} não encontrado." >&2
  echo "[dev.sh] Crie o virtualenv: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi
if [[ ! -d "${REPO_ROOT}/frontend/node_modules" ]]; then
  echo "[dev.sh] ERRO: frontend/node_modules ausente." >&2
  echo "[dev.sh] Rode: npm --prefix frontend install" >&2
  exit 1
fi

# ── Banner ────────────────────────────────────────────────────────────────────
cat <<EOF
[dev.sh] AP2WEB — desenvolvimento local
  backend  →  http://127.0.0.1:${PORT}  (FastAPI / uvicorn)
  frontend →  http://localhost:${FRONTEND_PORT}  (Vite)
  DB       →  SQLite em ${AP2WEB_DB_PATH}
  worker   →  ${AP2WEB_ENABLE_WORKER} (produção: python -m backend.app.worker)
  systemd  →  gerenciamento ${AP2WEB_MANAGE_SYSTEMD}
  secret   →  ${AP2WEB_SECRET:0:8}… (dev placeholder OK em AP2WEB_ENV=development)
EOF

# ── Port preflight ────────────────────────────────────────────────────────────
# Detect which process owns a port and report actionable info (never kill it).
_port_owner() {
  local port="$1"
  ss -ltnp 2>/dev/null | awk -v p=":${port} " '$4 ~ p {print $0}'
}
if owner=$( _port_owner "${PORT}" ); then
  echo "[dev.sh] ERRO: porta ${PORT} já está em uso." >&2
  echo "[dev.sh] Processo atualmente ouvindo:" >&2
  echo "   ${owner}" >&2
  echo "[dev.sh] Opções: pare o processo você mesmo, defina PORT=outra porta," >&2
  echo "[dev.sh]          ou AP2WEB_MANAGE_SYSTEMD=true para auto-gerenciar serviços systemd." >&2
  exit 1
fi
if owner=$( _port_owner "${FRONTEND_PORT}" ); then
  echo "[dev.sh] ERRO: porta ${FRONTEND_PORT} já está em uso." >&2
  echo "[dev.sh] Processo atualmente ouvindo:" >&2
  echo "   ${owner}" >&2
  exit 1
fi

# ── Optional systemd management (explicitly opted-in) ─────────────────────────
if [[ "${AP2WEB_MANAGE_SYSTEMD}" == "true" ]]; then
  for svc in ap2web-backend.service ap2web-frontend.service; do
    if systemctl --user is-active --quiet "${svc}" 2>/dev/null; then
      echo "[dev.sh] Parando serviço systemd ${svc} (AP2WEB_MANAGE_SYSTEMD=true)…"
      systemctl --user stop "${svc}" 2>/dev/null || true
    fi
  done
else
  echo "[dev.sh] Portas livres; nenhum serviço systemd foi parado (AP2WEB_MANAGE_SYSTEMD=false)."
fi

# ── Start backend (own process group, so cleanup only touches our children) ──
echo "[dev.sh] Iniciando backend…"
setsid "${VENV_UVICORN}" backend.app.main:app \
  --host 127.0.0.1 \
  --port "${PORT}" \
  < /dev/null &
BACKEND_PID=$!
BACKEND_PGID=$( ps -o pgid= -p "${BACKEND_PID}" 2>/dev/null | tr -d ' ' )
[[ -n "${BACKEND_PGID}" ]] || BACKEND_PGID="${BACKEND_PID}"

backend_ready=0
for _ in $(seq 1 50); do
  if curl --silent --show-error --fail --max-time 1 "http://127.0.0.1:${PORT}/api/ready" >/dev/null 2>&1; then
    echo "[dev.sh] backend pronto (/api/ready)."
    backend_ready=1
    break
  fi
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    echo "[dev.sh] ERRO: backend morreu durante inicialização." >&2
    exit 1
  fi
  sleep 0.2
done
if [[ ${backend_ready} -ne 1 ]]; then
  echo "[dev.sh] ERRO: backend não ficou pronto em 10s (/api/ready)." >&2
  exit 1
fi

# ── Start frontend (own process group) ────────────────────────────────────────
echo "[dev.sh] Iniciando frontend…"
setsid npm --prefix "${REPO_ROOT}/frontend" run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}" \
  < /dev/null &
FRONTEND_PID=$!
FRONTEND_PGID=$( ps -o pgid= -p "${FRONTEND_PID}" 2>/dev/null | tr -d ' ' )
[[ -n "${FRONTEND_PGID}" ]] || FRONTEND_PGID="${FRONTEND_PID}"

# ── Cleanup: only our own process groups ──────────────────────────────────────
_ap2web_kill_group() {
  local pgid="$1" sig="$2"
  [[ -n "${pgid}" ]] || return 0
  # Negative PID = send to the whole process group we created via setsid.
  kill "-${sig}" -- "-${pgid}" 2>/dev/null || true
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  set +e
  echo "[dev.sh] Encerrando processos filhos…" >&2
  _ap2web_kill_group "${BACKEND_PGID}" TERM
  _ap2web_kill_group "${FRONTEND_PGID}" TERM
  for _ in $(seq 1 15); do
    local alive=0
    [[ -n "${BACKEND_PID}"  ]] && kill -0 "${BACKEND_PID}"  2>/dev/null && alive=1
    [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null && alive=1
    [[ ${alive} -eq 0 ]] && break
    sleep 0.2
  done
  _ap2web_kill_group "${BACKEND_PGID}" KILL
  _ap2web_kill_group "${FRONTEND_PGID}" KILL
  if [[ ${exit_code} -ne 0 ]]; then
    echo "[dev.sh] Encerrado com código ${exit_code}." >&2
  else
    echo "[dev.sh] Encerrado." >&2
  fi
  exit "${exit_code}"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# ── Wait for either child to exit ────────────────────────────────────────────
wait -n "${BACKEND_PID}" "${FRONTEND_PID}"
status=$?
echo "[dev.sh] Um processo filho encerrou (status=${status}). Limpando…"
exit "${status}"