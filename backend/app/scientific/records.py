"""Canonical prediction records, scoring helpers and shared constants."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


_MATCH_COLUMNS = (
    "id", "league_id", "kickoff_datetime", "home_team_id", "away_team_id",
    "status", "score_home", "score_away", "xg_home", "xg_away",
)
_OUTCOMES = ("1", "X", "2")
_NEUTRAL_POISSON_PARAMETERS = {"lam_home": 1.2, "lam_away": 1.2, "rho": 0.0}
def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _metric_records(backtest_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Accept only complete canonical per-match 1X2 prediction records."""
    records = backtest_result.get("predictions", [])
    if not isinstance(records, Sequence):
        return []
    valid = []
    for record in records:
        if not isinstance(record, Mapping) or record.get("actual") not in _OUTCOMES:
            continue
        probabilities = record.get("probabilities")
        if not isinstance(probabilities, Mapping):
            continue
        try:
            probs = {outcome: float(probabilities[outcome]) for outcome in _OUTCOMES}
        except (KeyError, TypeError, ValueError):
            continue
        if (all(math.isfinite(value) and 0 <= value <= 1 for value in probs.values())
                and math.isclose(sum(probs.values()), 1.0, rel_tol=0.0, abs_tol=1e-9)):
            valid.append({"match_id": record.get("match_id"), "actual": record["actual"],
                          "probabilities": probs})
    return valid
def _brier(record: Mapping[str, Any]) -> float:
    return sum((record["probabilities"][outcome] - (outcome == record["actual"])) ** 2
               for outcome in _OUTCOMES)
def _log_loss(record: Mapping[str, Any]) -> float:
    return -math.log(max(record["probabilities"][record["actual"]], 1e-10))
def _outcome(row: Mapping[str, Any]) -> str:
    return "1" if row["score_home"] > row["score_away"] else (
        "X" if row["score_home"] == row["score_away"] else "2")
def _one_x_two_from_matrix(matrix: Sequence[Sequence[float]]) -> dict[str, float]:
    return {
        "1": sum(matrix[home][away] for home in range(len(matrix)) for away in range(home)),
        "X": sum(matrix[goal][goal] for goal in range(len(matrix))),
        "2": sum(matrix[home][away] for home in range(len(matrix)) for away in range(home + 1, len(matrix))),
    }
def _scored_match_ids(backtest_result: Mapping[str, Any]) -> set[int]:
    ids = set()
    for record in _metric_records(backtest_result):
        match_id = record.get("match_id")
        if isinstance(match_id, int) and not isinstance(match_id, bool):
            ids.add(match_id)
    return ids
