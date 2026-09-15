"""Append-only, timestamped external odds quotes."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from . import db

OUTCOMES = ("1", "X", "2")


def save_1x2_quote(match_id: int, provider: str, captured_at: str,
                   odds: dict[str, float], source_event_id: str | None = None) -> None:
    if match_id < 1 or not provider.strip():
        raise ValueError("match_id and provider are required")
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("captured_at must be ISO-8601") from exc
    if set(odds) != set(OUTCOMES):
        raise ValueError("1x2 quote requires outcomes 1, X, and 2")
    values = []
    for outcome in OUTCOMES:
        value = float(odds[outcome])
        if not math.isfinite(value) or value <= 1:
            raise ValueError("decimal odds must be finite and greater than 1")
        values.append((match_id, "1x2", outcome, value, provider.strip(), captured_at, source_event_id))
    for value in values:
        db.run_exec(
            "INSERT INTO odds_quotes(match_id,market_type,outcome,decimal_odd,provider,captured_at,source_event_id) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(match_id,market_type,outcome,provider,captured_at) DO NOTHING",
            value,
        )


def latest_1x2_quote(match_id: int, as_of: str | None = None) -> dict | None:
    cutoff = as_of or datetime.now(timezone.utc).isoformat()
    rows = db.run_query(
        "SELECT provider,captured_at,outcome,decimal_odd FROM odds_quotes "
        "WHERE match_id=? AND market_type='1x2' AND datetime(captured_at) <= datetime(?) "
        "ORDER BY captured_at DESC, id DESC", (match_id, cutoff))
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        key = (row["provider"], row["captured_at"])
        grouped.setdefault(key, {})[row["outcome"]] = float(row["decimal_odd"])
    for (provider, captured_at), odds in grouped.items():
        if set(odds) == set(OUTCOMES):
            return {"provider": provider, "captured_at": captured_at, "odds": odds}
    return None
