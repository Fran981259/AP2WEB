"""Durable audit log: redaction, persistence, health and retention."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid

from fastapi import Request

from .. import config
from ..columns import AUDIT_EVENTS
from .core import _audit_lock, client_ip, logger, request_id


def _event_id() -> str:
    return f"{int(time.time()):x}-{uuid.uuid4().hex[:12]}"


# Consecutive audit-persistence failures (health signal for /api/ready).
_audit_persistence_failures = 0
_AUDIT_HEALTH_LOCK = threading.Lock()
def _recursive_redact(value, depth: int = 0):
    """Recursively strip sensitive keys and hash their string values.

    Walk arbitrary nested dict/list structures so nested payloads (e.g.
    ``{"request": {"password": ...}}``) cannot slip past a shallow pass.
    Long strings are truncated to keep rows bounded.
    """
    if depth >= 8:
        return "[truncated]"
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            kk = str(k).strip().lower()
            if kk in _SENSITIVE_KEYS:
                out[k] = f"sha256:{_hash_value(v)[:16]}" if isinstance(v, str) and v else "[redacted]"
            else:
                out[k] = _recursive_redact(v, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_recursive_redact(x, depth + 1) for x in value]
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + "…[truncated]"
    return value
def _audit_record_success() -> None:
    global _audit_persistence_failures
    with _AUDIT_HEALTH_LOCK:
        _audit_persistence_failures = 0


def _audit_record_failure() -> None:
    global _audit_persistence_failures
    with _AUDIT_HEALTH_LOCK:
        _audit_persistence_failures += 1


def audit_failure_count() -> int:
    with _AUDIT_HEALTH_LOCK:
        return _audit_persistence_failures


def audit_persistence_healthy() -> bool:
    return audit_failure_count() == 0
def audit_event(request: Request | None = None, *, action: str, success: bool = True,
                error_code: str | None = None, metadata: dict | None = None,
                username: str | None = None, role: str | None = None,
                resource_type: str | None = None, resource_id: str | int | None = None,
                user_id: int | None = None) -> None:
    """Persist a durable audit record. Never raise — auditing must not crash requests."""
    eid = _event_id()
    rec = {
        "event_id": eid,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_id": request_id(request) if request else None,
        "username": username,
        "role": role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id is not None else None,
        "source_ip": client_ip(request) if request else None,
        "user_agent": (request.headers.get("User-Agent") or None) if request else None,
        "success": bool(success),
        "error_code": error_code,
        # Redacted recursively BEFORE anything leaves the module.
        "metadata": json.dumps(redact(metadata) or {}, ensure_ascii=False)[:2000],
    }
    # Structured log line (structured JSON even when persistence fails).
    try:
        logging.getLogger("ap2web.audit").info(json.dumps(rec, ensure_ascii=False))
    except Exception:
        pass
    try:
        from .. import db

        with _audit_lock:
            db.run_exec(
                "INSERT INTO audit_events(event_id,ts,request_id,user_id,username,role,action,"
                "resource_type,resource_id,source_ip,user_agent,success,error_code,metadata) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rec["event_id"], rec["ts"], rec["request_id"], user_id, rec["username"], rec["role"],
                 rec["action"], rec["resource_type"], rec["resource_id"], rec["source_ip"],
                 rec["user_agent"], 1 if rec["success"] else 0, rec["error_code"], rec["metadata"]),
            )
    except Exception as first:
        # One immediate retry for transient failures before flagging the record.
        try:
            with _audit_lock:
                db.run_exec(
                    "INSERT INTO audit_events(event_id,ts,request_id,user_id,username,role,action,"
                    "resource_type,resource_id,source_ip,user_agent,success,error_code,metadata) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rec["event_id"], rec["ts"], rec["request_id"], user_id, rec["username"], rec["role"],
                     rec["action"], rec["resource_type"], rec["resource_id"], rec["source_ip"],
                     rec["user_agent"], 1 if rec["success"] else 0, rec["error_code"], rec["metadata"]),
                )
            _audit_record_success()
            return
        except Exception:
            pass
        _audit_record_failure()
        # CRITICAL: audit loss is a security-relevant event. Metadata was already
        # redacted; the details below reference the event id, never raw secrets.
        logger.critical(
            "audit persistence failed action=%s event=%s first_err=%s",
            action, eid, type(first).__name__,
        )
def audit_ratelimit(request: Request, limit_name: str) -> None:
    audit_event(request, action="ratelimit.hit", success=False, error_code="RATE_LIMITED",
                metadata={"limit": limit_name})
def admin_audit_records(limit: int = 100, action: str | None = None) -> list[dict]:
    from .. import db

    limit = max(1, min(int(limit), 500))
    q = f"SELECT {AUDIT_EVENTS} FROM audit_events"
    conds: list[str] = []
    params: list = []
    if action:
        conds.append("action=?")
        params.append(action)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db.run_query(q, tuple(params))]
def prune_audit_log(older_than_days: int | None = None) -> int:
    """Apply the retention policy; returns number of pruned rows."""
    from .. import db

    keep = older_than_days or config.settings.audit_retention_days
    try:
        # ISO UTC timestamps sort lexically; prune very old rows.
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - keep * 86400))
        rc = db.run_exec("DELETE FROM audit_events WHERE ts < ?", (cutoff,))
        return int(rc or 0)
    except Exception as e:
        logger.warning("audit prune failed: %s", type(e).__name__)
        return 0
_SENSITIVE_KEYS = {
    "password", "passwd", "pwd", "secret", "token", "access_token", "refresh_token",
    "csrf", "csrf_token", "cookie", "authorization", "api_key", "apikey", "auth",
}


def redact(metadata: dict | None) -> dict | None:
    """Recursively strip any secrets/passwords/tokens before logging/persisting.

    Sensitive keys are dropped or hashed; arbitrary nesting is handled so a
    request body that embeds credentials inside nested objects is still safe.
    """
    if not metadata:
        return None
    out = _recursive_redact(metadata)
    return out if out else None
def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
