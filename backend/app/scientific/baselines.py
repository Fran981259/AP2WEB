"""Baseline predictions, baseline evaluations and candidate comparison."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..model import build_matrix
from .metrics import scientific_metrics
from .records import (
    _NEUTRAL_POISSON_PARAMETERS,
    _OUTCOMES,
    _one_x_two_from_matrix,
    _outcome,
    _scored_match_ids,
)


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
