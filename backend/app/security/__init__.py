"""Security primitives — CSRF, audit persistence, headers, safe errors (Phase 2)."""
from __future__ import annotations

from .audit import (
    admin_audit_records,
    audit_event,
    audit_failure_count,
    audit_persistence_healthy,
    audit_ratelimit,
    prune_audit_log,
    redact,
)
from .core import SecurityError, client_ip, request_id
from .csrf import csrf_protect, generate_csrf_token
from .errors import error_code_for, safe_error_body

__all__ = [
    "SecurityError",
    "admin_audit_records",
    "audit_event",
    "audit_failure_count",
    "audit_persistence_healthy",
    "audit_ratelimit",
    "client_ip",
    "csrf_protect",
    "error_code_for",
    "generate_csrf_token",
    "prune_audit_log",
    "redact",
    "request_id",
    "safe_error_body",
]
