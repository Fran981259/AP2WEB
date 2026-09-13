"""Runtime HTTP smoke suite for the real Uvicorn process.

This is intentionally separate from in-process unit tests: it validates the
same network path used by deployment without sharing SQLite connections or
rate-limit state with pytest.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


PORT = int(os.environ.get("AP2WEB_RUNTIME_TEST_PORT", "18767"))
BASE = f"http://127.0.0.1:{PORT}"


def _get(path: str) -> tuple[int, str, dict[str, str]]:
    request = urllib.request.Request(f"{BASE}{path}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(), dict(error.headers)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ap2web_runtime_") as tmp:
        env = os.environ.copy()
        env.update({
            "AP2WEB_ENV": "development",
            "AP2WEB_SECRET": "runtime-test-secret-do-not-use-in-production-0123456789",
            "AP2WEB_DB_PATH": os.path.join(tmp, "runtime.db"),
            "AP2WEB_ENABLE_WORKER": "false",
            "AP2WEB_RATE_LIMIT_STORAGE": "memory",
            "AP2WEB_PBKDF2_ITERATIONS": "10000",
        })
        command = [sys.executable, "-m", "uvicorn", "backend.app.main:app",
                   "--host", "127.0.0.1", "--port", str(PORT)]
        process = subprocess.Popen(command, cwd=os.getcwd(), env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True)
        try:
            deadline = time.time() + 15
            while time.time() < deadline:
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    raise RuntimeError(f"Uvicorn exited early:\n{output}")
                try:
                    status, _, _ = _get("/api/ready")
                    if status == 200:
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Uvicorn did not become ready")

            health_status, health_body, headers = _get("/api/health")
            assert health_status == 200, health_body
            assert '"ok":true' in health_body
            normalized_headers = {key.lower(): value for key, value in headers.items()}
            assert normalized_headers.get("x-content-type-options") == "nosniff"

            ready_status, ready_body, _ = _get("/api/ready")
            assert ready_status == 200, ready_body
            assert '"ready":true' in ready_body
            print("[runtime] health/readiness/security headers: PASS")
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
