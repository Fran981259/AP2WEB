"""Temporal K-fold cross-validation with zero leakage."""
from __future__ import annotations

import math
from collections import deque

from .. import db, execution_store
from ..feature_engine import compute_match_stats, compute_team_stats
from ..learning import MIN_SAMPLES
from ..model import MatchInput, TeamInput, predict as run_predict
from .executions import _finish_execution, _snapshot_metadata


def temporal_cv(league_id: int, n_folds: int = 5,
                feature: str = "xg", window: int = 10,
                home_adv: float = 1.15, rho: float = 0.0) -> dict:
    """Cross-validation temporal em K folds.

    Divide o histórico em K partes cronológicas iguais.
    Para cada fold i (1..K-1): treina nos folds 0..i-1, testa no i.
    Retorna métricas por fold e agregadas.
    """
    matches = db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "       m.xg_home, m.xg_away, m.score_home, m.score_away "
        "FROM matches m "
        "WHERE m.league_id=? AND m.status='played' "
        "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
        "ORDER BY m.kickoff_datetime, m.id", (league_id,))

    if len(matches) < MIN_SAMPLES:
        return {"folds": [], "mean_accuracy": 0.0, "mean_brier": 0.0,
                "std_accuracy": 0.0, "std_brier": 0.0, "total_matches": len(matches),
                "n_folds": 0}

    fold_size = len(matches) // n_folds
    if fold_size < 5:
        n_folds = max(2, len(matches) // 5)
        fold_size = len(matches) // n_folds

    folds = []
    for fold_idx in range(1, n_folds):
        train_end = fold_idx * fold_size
        test_start = train_end
        test_end = min(test_start + fold_size, len(matches))

        test_matches = matches[test_start:test_end]
        if len(test_matches) < 3:
            continue

        hist: dict[int, deque] = {}
        correct = 0
        brier_sum = 0.0
        total = 0

        # Pré-carrega histórico com todos os jogos antes do teste
        for m in matches[:train_end]:
            hid, aid = m["home_team_id"], m["away_team_id"]
            gm = compute_match_stats({
                "score_home": m["score_home"],
                "score_away": m["score_away"],
                "xg_home": m["xg_home"],
                "xg_away": m["xg_away"],
            }, feature)
            gh, ga = gm["gf"], gm["ga"]
            hh = hist.setdefault(hid, deque(maxlen=window))
            ah = hist.setdefault(aid, deque(maxlen=window))
            hh.appendleft({"gf": gh, "ga": ga})
            ah.appendleft({"gf": ga, "ga": gh})

        # Test simultaneous fixtures before adding any of their outcomes.
        index = 0
        while index < len(test_matches):
            kickoff = test_matches[index]["kickoff_datetime"]
            batch = []
            while index < len(test_matches) and test_matches[index]["kickoff_datetime"] == kickoff:
                batch.append(test_matches[index])
                index += 1
            for m in batch:
                hid, aid = m["home_team_id"], m["away_team_id"]
                hh, ah = hist.get(hid), hist.get(aid)
                if hh is None or ah is None or not hh or not ah:
                    continue
                home_l = compute_team_stats(hh, window, feature)
                away_l = compute_team_stats(ah, window, feature)
                mi = MatchInput(home=TeamInput(name="h", gf_avg=home_l.get("gf_avg", 0), ga_avg=home_l.get("ga_avg", 0)), away=TeamInput(name="a", gf_avg=away_l.get("gf_avg", 0), ga_avg=away_l.get("ga_avg", 0)))
                p = run_predict(mi, home_advantage=home_adv, rho=rho).probs["1x2"]
                actual = "1" if m["score_home"] > m["score_away"] else ("X" if m["score_home"] == m["score_away"] else "2")
                correct += int(max(p, key=p.get) == actual)
                brier_sum += (1 - p[actual]) ** 2 + sum(p[k] ** 2 for k in p if k != actual)
                total += 1
            for m in batch:
                hid, aid = m["home_team_id"], m["away_team_id"]
                gm = compute_match_stats({"score_home": m["score_home"], "score_away": m["score_away"], "xg_home": m["xg_home"], "xg_away": m["xg_away"]}, feature)
                hist.setdefault(hid, deque(maxlen=window)).appendleft({"gf": gm["gf"], "ga": gm["ga"]})
                hist.setdefault(aid, deque(maxlen=window)).appendleft({"gf": gm["ga"], "ga": gm["gf"]})

        if total > 0:
            folds.append({
                "fold": fold_idx,
                "train_size": train_end,
                "test_size": len(test_matches),
                "accuracy": round(correct / total * 100, 2),
                "brier": round(brier_sum / total, 4),
                "correct": correct,
                "total": total,
            })

    if not folds:
        return {"folds": [], "mean_accuracy": 0.0, "mean_brier": 0.0,
                "std_accuracy": 0.0, "std_brier": 0.0, "total_matches": len(matches),
                "n_folds": 0}

    accs = [f["accuracy"] for f in folds]
    briers = [f["brier"] for f in folds]
    mean_acc = sum(accs) / len(accs)
    mean_brier = sum(briers) / len(briers)
    std_acc = math.sqrt(sum((a - mean_acc) ** 2 for a in accs) / len(accs)) if len(accs) > 1 else 0
    std_brier = math.sqrt(sum((b - mean_brier) ** 2 for b in briers) / len(briers)) if len(briers) > 1 else 0

    return {
        "folds": folds,
        "mean_accuracy": round(mean_acc, 2),
        "mean_brier": round(mean_brier, 4),
        "std_accuracy": round(std_acc, 2),
        "std_brier": round(std_brier, 4),
        "total_matches": len(matches),
        "n_folds": len(folds),
    }


def run_temporal_cv(league_id: int, n_folds: int = 5) -> dict:
    """Run the public CV operation with an auditable execution lifecycle."""
    _manifest, snapshot = _snapshot_metadata(league_id)
    parameters = {
        "scope": "temporal_cv_endpoint",
        "league_id": league_id,
        "requested_n_folds": n_folds,
        "effective_parameters": {
            "feature": "xg", "window": 10, "home_adv": 1.15, "rho": 0.0,
        },
    }
    execution = execution_store.start(
        execution_type="temporal_cv", snapshot_hash=snapshot["hash"], parameters=parameters)
    try:
        result = temporal_cv(league_id, n_folds)
    except Exception as error:
        _finish_execution(execution["execution_id"], "failed", {
            "snapshot_manifest": snapshot,
            "error": str(error)[:2000],
        })
        raise
    _finish_execution(execution["execution_id"], "completed", {
        "snapshot_manifest": snapshot,
        "effective_parameters": {
            **parameters["effective_parameters"],
            "n_folds": result["n_folds"],
        },
        "metrics": {
            "mean_accuracy": result["mean_accuracy"],
            "mean_brier": result["mean_brier"],
            "n_folds": result["n_folds"],
            "total_matches": result["total_matches"],
        },
        "results": result,
    })
    return result
