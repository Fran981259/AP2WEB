"""Descriptive, matched-cohort model diagnostics; never certifies generalization.

Only records created AND predicted strictly before kickoff are eligible. The
full 1X2 vector is rescored against the match result; stored binary pick Brier
is deliberately not compared with multiclass Brier. Results are grouped by
league/model version and deduplicated by match. No database writes.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict

from . import db

OUTCOMES = ("1", "X", "2")
BASELINE = {"1": 0.45, "X": 0.28, "2": 0.27}


def brier_multiclasse(probs: dict, actual: str) -> float:
    return sum((probs[k] - int(k == actual)) ** 2 for k in OUTCOMES)


def diagnose(league_id: int | None = None, min_sample: int = 30) -> dict:
    query = (
        "SELECT p.id, p.league_id, p.match_id, p.model_version, p.payload, "
        "m.score_home, m.score_away FROM predictions p "
        "JOIN matches m ON m.id=p.match_id AND m.league_id=p.league_id "
        "WHERE p.pick_type='1X2' AND m.status='played' "
        "AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL "
        "AND datetime(p.created_at)<datetime(m.kickoff_datetime) "
        "AND datetime(p.predicted_at)<datetime(m.kickoff_datetime) "
        "AND p.model_version IS NOT NULL ")
    params = ()
    if league_id is not None:
        query += "AND p.league_id=? "
        params = (league_id,)
    query += "ORDER BY p.id"
    groups = defaultdict(list)
    seen = set()
    invalid = 0
    for row in db.run_query(query, params):
        key = (row["league_id"], row["model_version"], row["match_id"])
        if key in seen:
            continue
        try:
            probs = json.loads(row["payload"])["probs"]["1x2"]
            if set(probs) != set(OUTCOMES) or not all(
                    isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1
                    for v in probs.values()) or not math.isclose(sum(probs.values()), 1, abs_tol=1e-6):
                raise ValueError("invalid probability vector")
        except (TypeError, ValueError, KeyError):
            invalid += 1
            continue
        seen.add(key)
        actual = "1" if row["score_home"] > row["score_away"] else (
            "X" if row["score_home"] == row["score_away"] else "2")
        groups[key[:2]].append((brier_multiclasse(probs, actual), brier_multiclasse(BASELINE, actual)))
    results = []
    for (lid, version), pairs in sorted(groups.items()):
        n = len(pairs)
        results.append({"league_id": lid, "model_version": version, "n": n,
                        "brier_multiclass": sum(p[0] for p in pairs) / n,
                        "baseline_brier_same_matches": sum(p[1] for p in pairs) / n,
                        "delta_brier": sum(p[0] - p[1] for p in pairs) / n,
                        "status": "descriptive_only" if n >= min_sample else "insufficient_sample"})
    return {"cohorts": results, "invalid_payloads": invalid,
            "method": "paired multiclass Brier; earliest eligible record per match/version",
            "limitation": "timestamps/payloads are not tamper-proof; no significance, calibration or profitability certification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league-id", type=int)
    parser.add_argument("--min-sample", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(diagnose(args.league_id, args.min_sample), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
