"""Dataset snapshot: completed rows, manifest hash and temporal split."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from .. import db
from .records import _MATCH_COLUMNS


def _completed_rows(league_id: int | None = None) -> list[dict[str, Any]]:
    where = "WHERE m.status='played' AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL"
    params: tuple[Any, ...] = ()
    if league_id is not None:
        where += " AND m.league_id=?"
        params = (league_id,)
    rows = db.run_query(
        "SELECT " + ", ".join(f"m.{column}" for column in _MATCH_COLUMNS) + " "
        "FROM matches m " + where + " ORDER BY m.kickoff_datetime, m.id",
        params,
    )
    return [dict(row) for row in rows]
def _is_usable(row: Mapping[str, Any]) -> bool:
    return all(row.get(field) is not None for field in (
        "id", "league_id", "kickoff_datetime", "home_team_id", "away_team_id",
        "score_home", "score_away",
    ))
def build_snapshot_manifest(league_id: int | None = None) -> dict[str, Any]:
    """Return a stable manifest and SHA-256 digest of completed match facts."""
    rows = _completed_rows(league_id)
    payload = {"league_id": league_id, "matches": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "league_id": league_id,
        "completed_match_count": len(rows),
        "usable_match_count": sum(_is_usable(row) for row in rows),
        "matches": rows,
        "hash": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }
def temporal_split(rows: Sequence[Mapping[str, Any]], holdout_fraction: float = 0.2) -> dict[str, list[dict[str, Any]]]:
    """Split chronological rows with the newest observations reserved as holdout."""
    if isinstance(holdout_fraction, bool) or not isinstance(holdout_fraction, (int, float)):
        raise ValueError("holdout_fraction must be a number between 0 and 0.5")
    if not 0 < holdout_fraction <= 0.5:
        raise ValueError("holdout_fraction must be between 0 and 0.5")
    ordered = sorted((dict(row) for row in rows), key=lambda row: (row["kickoff_datetime"], row["id"]))
    if len(ordered) < 2:
        return {"development": ordered, "holdout": []}
    holdout_size = max(1, math.ceil(len(ordered) * holdout_fraction))
    split_at = len(ordered) - holdout_size
    # A simultaneous kickoff must not be split: its outcomes are unavailable
    # to every other fixture in that batch.
    while split_at > 0 and ordered[split_at - 1]["kickoff_datetime"] == ordered[split_at]["kickoff_datetime"]:
        split_at -= 1
    return {"development": ordered[:split_at], "holdout": ordered[split_at:]}
