"""Append-only execution lifecycle records for auditable CLI operations."""
from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from . import db
from .columns import EXECUTION_EVENTS, prefixed


def canonical_json(value: Mapping[str, Any]) -> str:
    """Serialize structured event data in one stable representation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _event(row: Mapping[str, Any]) -> dict[str, Any]:
    event = dict(row)
    for field in ("parameters", "results"):
        if event[field] is not None:
            event[field] = json.loads(event[field])
    return event


def start(*, execution_type: str, snapshot_hash: str, parameters: Mapping[str, Any],
          execution_id: str | None = None) -> dict[str, Any]:
    """Append a started event and return its immutable record."""
    if not execution_type or not snapshot_hash:
        raise ValueError("execution_type and snapshot_hash are required")
    execution_id = execution_id or str(uuid.uuid4())
    ts = _now()
    db.run_exec(
        "INSERT INTO execution_events("
        "execution_id,execution_type,event_type,status,ts,snapshot_hash,parameters"
        ") VALUES(?,?,?,?,?,?,?)",
        (execution_id, execution_type, "started", "started", ts, snapshot_hash,
         canonical_json(parameters)),
    )
    return get(execution_id)


def finish(*, execution_id: str, status: str, artifact_content_hash: str,
           results: Mapping[str, Any]) -> dict[str, Any]:
    """Append a terminal event; existing lifecycle records are never changed."""
    if not execution_id or not status or not artifact_content_hash:
        raise ValueError("execution_id, status, and artifact_content_hash are required")
    previous = get(execution_id)
    if previous is None:
        raise ValueError("execution must be started before it can finish")
    if previous["event_type"] == "finished":
        raise ValueError("execution already has a terminal event")
    ts = _now()
    db.run_exec(
        "INSERT INTO execution_events("
        "execution_id,execution_type,event_type,status,ts,snapshot_hash,parameters,"
        "artifact_content_hash,results"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (execution_id, previous["execution_type"], "finished", status, ts,
         previous["snapshot_hash"], canonical_json(previous["parameters"]),
         artifact_content_hash, canonical_json(results)),
    )
    return get(execution_id)


def get(execution_id: str) -> dict[str, Any] | None:
    """Return the latest event-derived state for one logical execution."""
    rows = db.run_query(
        f"SELECT {EXECUTION_EVENTS} FROM execution_events "
        "WHERE execution_id=? ORDER BY id DESC LIMIT 1",
        (execution_id,),
    )
    return _event(rows[0]) if rows else None


def list(*, execution_type: str | None = None) -> list[dict[str, Any]]:
    """Return one latest event-derived state per execution, newest first."""
    where = ""
    params: tuple[Any, ...] = ()
    if execution_type is not None:
        where = "WHERE execution_type=?"
        params = (execution_type,)
    rows = db.run_query(
        f"SELECT {prefixed(EXECUTION_EVENTS, 'e')} FROM execution_events e "
        "JOIN (SELECT execution_id, MAX(id) AS latest_id FROM execution_events "
        f"{where} GROUP BY execution_id) latest ON latest.latest_id=e.id "
        "ORDER BY e.id DESC",
        params,
    )
    return [_event(row) for row in rows]
