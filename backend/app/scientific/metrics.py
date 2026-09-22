"""Protocol metrics: Brier, log-loss, RPS, calibration and bootstrap."""
from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .records import (
    _OUTCOMES,
    _brier,
    _log_loss,
    _mean,
    _metric_records,
)


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
