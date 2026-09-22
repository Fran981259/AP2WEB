"""Top-level scientific protocol evaluation (no persistence, no promotion)."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .. import learning
from .baselines import _baseline_evaluations, _comparison
from .metrics import scientific_metrics
from .snapshot import _is_usable, build_snapshot_manifest, temporal_split


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
