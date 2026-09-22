"""Auth core: logger, constants, roles/permissions table, bearer scheme."""
from __future__ import annotations

import logging
import re
import time

from fastapi.security import HTTPBearer


logger = logging.getLogger("ap2web.auth")

ALGO = "HS256"
_TOKEN_PREFIX = "Bearer "

VALID_ROLES = {"user", "operator", "admin"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Permissões por papel (deny-by-default; admin = "*").
PERMISSIONS: dict[str, set] = {
    "user": {
        "read:leagues", "read:teams", "read:matches", "read:predictions",
        "read:history", "read:jobs", "read:market", "read:risk",
    },
    "operator": {
        "read:leagues", "read:teams", "read:matches", "read:predictions",
        "read:history", "read:jobs", "read:market", "read:risk",
        "sync:data", "sync:league", "job:cancel",
    },
    "admin": {"*"},
}

_bearer = HTTPBearer(auto_error=False)
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _iso_after(seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + seconds))
