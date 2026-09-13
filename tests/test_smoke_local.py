"""AP2WEB — local development smoke test.

Validates that:
1. Frontend root (http://127.0.0.1:5173) returns HTTP 200 and HTML.
2. Backend /api/health returns HTTP 200 and ok: true (liveness).
3. Backend /api/ready returns HTTP 200 ready: true (readiness).
4. Frontend /api/health proxy returns the same backend payload.
5. Frontend HTML contains the React root element.

Does NOT start any service; assumes `npm run dev` is already running.
Fails clearly if a service is unreachable.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

FRONTEND = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173")
BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
CHECK_FRONTEND = FRONTEND not in ("", "skip", "none", "0")
PROXY_HEALTH = os.environ.get("PROXY_HEALTH_URL", f"{FRONTEND}/api/health")
DIRECT_HEALTH = f"{BACKEND}/api/health"
DIRECT_READY = f"{BACKEND}/api/ready"
FRONTEND_ROOT = f"{FRONTEND}/"
TIMEOUT_SECONDS = 5.0


class SmokeFailure(Exception):
    pass


def _fetch(url: str, expect_json: bool = False) -> tuple[int, bytes]:
    deadline = time.time() + TIMEOUT_SECONDS
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_err = e
            time.sleep(0.25)
    raise SmokeFailure(f"Não foi possível conectar a {url}: {last_err}")


def _check_root_html() -> None:
    status, body = _fetch(FRONTEND_ROOT)
    if status != 200:
        raise SmokeFailure(f"frontend root status={status}, esperado 200")
    text = body.decode("utf-8", errors="replace")
    if "<div id=\"root\"" not in text and "<div id=root" not in text:
        raise SmokeFailure("frontend root não contém <div id=\"root\"> (não é SPA React)")
    print("  ✓ frontend root OK (HTTP 200, contém #root)")


def _check_direct_health() -> dict:
    status, body = _fetch(DIRECT_HEALTH)
    if status != 200:
        raise SmokeFailure(f"backend /api/health status={status}, esperado 200")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise SmokeFailure(f"backend /api/health não retornou JSON: {e}")
    if not data.get("ok"):
        raise SmokeFailure(f"backend /api/health ok=False: {data}")
    print(f"  ✓ backend /api/health OK (liveness, version={data.get('version')})")
    return data


def _check_ready() -> None:
    status, body = _fetch(DIRECT_READY)
    if status != 200:
        raise SmokeFailure(f"backend /api/ready status={status}, esperado 200")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise SmokeFailure(f"backend /api/ready não retornou JSON: {e}")
    if not data.get("ready"):
        raise SmokeFailure(f"backend /api/ready ready=False: {data}")
    checks = data.get("checks", {})
    if checks.get("startup") is not True or checks.get("database") is not True:
        raise SmokeFailure(f"backend /api/ready checks incompletos: {checks}")
    print(f"  ✓ backend /api/ready OK ({sorted(checks)})")


def _check_proxy_health() -> None:
    status, body = _fetch(PROXY_HEALTH)
    if status != 200:
        raise SmokeFailure(f"proxy /api/health status={status}, esperado 200")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise SmokeFailure(f"proxy /api/health não retornou JSON: {e}")
    if not data.get("ok"):
        raise SmokeFailure(f"proxy /api/health ok=False: {data}")
    print("  ✓ proxy /api/health OK (via Vite)")


def main() -> int:
    print("[smoke] AP2WEB — testes de fumaça do ambiente local")
    print(f"[smoke] FRONTEND={FRONTEND}  BACKEND={BACKEND}")
    if os.environ.get("AP2WEB_ENV") != "development":
        print("[smoke] AVISO: AP2WEB_ENV != development — checagem continua para diagnosticar o ambiente atual.")
    try:
        if CHECK_FRONTEND:
            _check_root_html()
        _check_direct_health()
        _check_ready()
        if CHECK_FRONTEND:
            _check_proxy_health()
    except SmokeFailure as e:
        print(f"[smoke] FALHOU: {e}", file=sys.stderr)
        return 1
    print("[smoke] Todos os checks passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
