"""In-memory, reproducible evaluation protocol for completed match data.

This module deliberately creates no database schema and never promotes models.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from . import db, learning
from .model import build_matrix


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


def _baseline_predictions(rows: Sequence[Mapping[str, Any]], scored_ids: set[int], *,
                          history: Sequence[Mapping[str, Any]] = (),
                          update_history: bool) -> dict[str, dict[str, Any]]:
    """Score target rows from prior history, updating only after each kickoff batch."""
    ordered = sorted((dict(row) for row in rows), key=lambda row: (row["kickoff_datetime"], row["id"]))
    outcomes = [_outcome(row) for row in history]
    empirical_predictions = []
    poisson_predictions = []
    index = 0
    while index < len(ordered):
        kickoff = ordered[index]["kickoff_datetime"]
        batch = []
        while index < len(ordered) and ordered[index]["kickoff_datetime"] == kickoff:
            batch.append(ordered[index])
            index += 1
        counts = {outcome: outcomes.count(outcome) for outcome in _OUTCOMES}
        total = len(outcomes)
        empirical = ({outcome: counts[outcome] / total for outcome in _OUTCOMES} if total else
                     {outcome: 1 / len(_OUTCOMES) for outcome in _OUTCOMES})
        poisson = _one_x_two_from_matrix(build_matrix(**_NEUTRAL_POISSON_PARAMETERS))
        for row in batch:
            if row["id"] in scored_ids:
                actual = _outcome(row)
                empirical_predictions.append(
                    {"match_id": row["id"], "actual": actual, "probabilities": dict(empirical)})
                poisson_predictions.append(
                    {"match_id": row["id"], "actual": actual, "probabilities": dict(poisson)})
        if update_history:
            outcomes.extend(_outcome(row) for row in batch)
    return {
        "league_empirical_1x2": {"total": len(empirical_predictions), "predictions": empirical_predictions},
        "neutral_independent_poisson": {"total": len(poisson_predictions), "predictions": poisson_predictions},
    }


def _baseline_evaluations(development: Sequence[Mapping[str, Any]], holdout: Sequence[Mapping[str, Any]],
                          development_result: Mapping[str, Any], holdout_result: Mapping[str, Any],
                          *, bootstrap_resamples: int, bootstrap_seed: int) -> dict[str, Any]:
    """Evaluate baselines on exactly the candidate's scored rows in each split."""
    development_predictions = _baseline_predictions(
        development, _scored_match_ids(development_result), update_history=True)
    # Holdout facts remain unavailable to every baseline holdout prediction.
    holdout_predictions = _baseline_predictions(
        holdout, _scored_match_ids(holdout_result), history=development, update_history=False)
    baselines = {
        "league_empirical_1x2": {
            "description": "League 1X2 empirical frequency from prior completed matches; uniform only before history exists.",
            "development": development_predictions["league_empirical_1x2"],
            "holdout": holdout_predictions["league_empirical_1x2"],
        },
        "neutral_independent_poisson": {
            "description": "Fixed neutral independent Poisson, not the candidate feature/model.",
            "parameters": dict(_NEUTRAL_POISSON_PARAMETERS),
            "development": development_predictions["neutral_independent_poisson"],
            "holdout": holdout_predictions["neutral_independent_poisson"],
        },
    }
    for baseline in baselines.values():
        for split_name in ("development", "holdout"):
            baseline["metrics"] = baseline.get("metrics", {}) | {
                split_name: scientific_metrics(
                    baseline[split_name], bootstrap_resamples=bootstrap_resamples,
                    bootstrap_seed=bootstrap_seed)
            }
    return baselines


def _comparison(candidate_metrics: Mapping[str, Any], baselines: Mapping[str, Any]) -> dict[str, Any]:
    """Report candidate and baseline metrics only; no selection conclusion is made."""
    return {
        "decision": "not_performed",
        "development": {
            "candidate": candidate_metrics["development"],
            "baselines": {name: baseline["metrics"]["development"]
                          for name, baseline in baselines.items()},
        },
        "holdout": {
            "candidate": candidate_metrics["holdout"],
            "baselines": {name: baseline["metrics"]["holdout"]
                          for name, baseline in baselines.items()},
        },
    }


def _bootstrap_interval(records: Sequence[Mapping[str, Any]], metric: Callable[[Mapping[str, Any]], float],
                        resamples: int, seed: int) -> dict[str, float]:
    generator = random.Random(seed)
    count = len(records)
    samples = sorted(
        _mean([metric(records[generator.randrange(count)]) for _ in range(count)])
        for _ in range(resamples)
    )
    return {"lower": samples[int((resamples - 1) * 0.025)],
            "upper": samples[int((resamples - 1) * 0.975)]}


def scientific_metrics(backtest_result: Mapping[str, Any], *, bootstrap_resamples: int = 1_000,
                       bootstrap_seed: int = 0) -> dict[str, Any]:
    """Calculate protocol metrics from canonical, per-match prediction facts."""
    if (isinstance(bootstrap_resamples, bool) or not isinstance(bootstrap_resamples, int)
            or bootstrap_resamples < 1):
        raise ValueError("bootstrap_resamples must be a positive integer")
    if isinstance(bootstrap_seed, bool) or not isinstance(bootstrap_seed, int):
        raise ValueError("bootstrap_seed must be an integer")
    records = _metric_records(backtest_result)
    if not records:
        return {"status": "insufficient_data", "reason": "no_scored_prediction_records", "samples": 0}
    calibration = {}
    for outcome in _OUTCOMES:
        predicted = _mean([record["probabilities"][outcome] for record in records])
        observed = _mean([float(record["actual"] == outcome) for record in records])
        calibration[outcome] = {"mean_predicted_probability": predicted,
                                "observed_frequency": observed,
                                "calibration_gap": observed - predicted}
    rps = _mean([
        sum((sum(record["probabilities"][outcome] for outcome in _OUTCOMES[:index + 1]) -
             float(record["actual"] in _OUTCOMES[:index + 1])) ** 2 for index in range(2)) / 2
        for record in records
    ])
    return {
        "status": "completed",
        "samples": len(records),
        "brier": _mean([_brier(record) for record in records]),
        "logloss": _mean([_log_loss(record) for record in records]),
        "rps": rps,
        "calibration": calibration,
        "bootstrap": {
            "resamples": bootstrap_resamples,
            "seed": bootstrap_seed,
            "brier": _bootstrap_interval(records, _brier, bootstrap_resamples, bootstrap_seed),
            "logloss": _bootstrap_interval(records, _log_loss, bootstrap_resamples, bootstrap_seed + 1),
        },
    }


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


def run_scientific_protocol(
    league_id: int | None = None,
    *,
    holdout_fraction: float = 0.2,
    backtest: Callable[[Sequence[Mapping[str, Any]]], Any] | None = None,
    fixed_parameters: Mapping[str, Any] | None = None,
    bootstrap_resamples: int = 1_000,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    """Evaluate a temporal split without persisting, selecting, or promoting.

    Fixed parameters are intentionally not calibrated here: existing calibration
    queries the database and cannot be limited to development rows.
    """
    manifest = build_snapshot_manifest(league_id)
    usable = [row for row in manifest["matches"] if _is_usable(row)]
    base = {
        "snapshot": {key: value for key, value in manifest.items() if key != "matches"},
        "promotion_enabled": False,
    }
    if not usable:
        return base | {"status": "blocked", "reason": "no_usable_dataset"}

    split = temporal_split(usable, holdout_fraction)
    if not split["holdout"] or not split["development"]:
        return base | {
            "status": "insufficient_data",
            "reason": "temporal_split_requires_at_least_two_matches",
            "split": split,
        }
    if fixed_parameters is not None:
        parameters = dict(fixed_parameters)
        development = learning.backtest_completed_matches(split["development"], **parameters)
        # Include development only as prior history; score exclusively holdout.
        holdout = learning.backtest_completed_matches(
            [*split["development"], *split["holdout"]],
            evaluation_start=len(split["development"]),
            **parameters,
        )
        development_metrics = scientific_metrics(
            development, bootstrap_resamples=bootstrap_resamples, bootstrap_seed=bootstrap_seed)
        holdout_metrics = scientific_metrics(
            holdout, bootstrap_resamples=bootstrap_resamples, bootstrap_seed=bootstrap_seed)
        metrics = {"development": development_metrics, "holdout": holdout_metrics}
        baselines = _baseline_evaluations(
            split["development"], split["holdout"], development, holdout,
            bootstrap_resamples=bootstrap_resamples, bootstrap_seed=bootstrap_seed)
        return base | {
            "status": "completed" if development_metrics["status"] == holdout_metrics["status"] == "completed"
            else "insufficient_data",
            "parameters": parameters,
            "parameter_selection": "not_performed_fixed_parameters",
            "split": split,
            "development": development,
            "holdout": holdout,
            "metrics": metrics,
            "baselines": baselines,
            "comparison": _comparison(metrics, baselines),
        }
    if backtest is not None:
        return base | {
            "status": "prepared",
            "backtest_source": "supplied",
            "split": split,
            "walk_forward": backtest(split["development"]),
            "reason": "holdout_evaluation_required_before_completion",
        }

    return base | {
        "status": "prepared",
        "reason": "fixed_parameters_required_for_canonical_evaluation",
        "split": split,
    }
