"""BacktestLoop detailed mixin: walk-forward evaluation and comparison."""
from __future__ import annotations

import json
import math
import os
from collections import deque

from .. import db
from ..feature_engine import compute_match_stats, compute_team_stats
from ..learning import MIN_SAMPLES
from . import paths


class LoopDetailedMixin:
    """Owns _backtest_detailed and _compare_with_previous."""


    def _backtest_detailed(self, league_id: int, home_adv: float = 1.15,
                           window: int = 10, feature: str = "xg",
                           rho: float = 0.0) -> dict:
        """Backtest detalhado com análise de erros e propostas."""
        from ..model import MatchInput, TeamInput, predict as run_predict

        matches = db.run_query(
            "SELECT m.id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
            "       m.xg_home, m.xg_away, m.score_home, m.score_away, "
            "       th.name AS home_name, ta.name AS away_name "
            "FROM matches m "
            "JOIN teams th ON th.id=m.home_team_id "
            "JOIN teams ta ON ta.id=m.away_team_id "
            "WHERE m.league_id=? AND m.status='played' "
            "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
            "ORDER BY m.kickoff_datetime, m.id", (league_id,))

        if len(matches) < MIN_SAMPLES:
            return {"accuracy": 0.0, "brier": 0.0, "logloss": 0.0,
                    "correct": 0, "wrong": 0, "total": len(matches),
                    "proposals": [], "error_analysis": {}, "series": []}

        hist: dict[int, deque] = {}
        correct = 0
        wrong = 0
        brier_sum = 0.0
        logloss_sum = 0.0
        total = 0
        series = []
        errors_by_type = {"1": 0, "X": 0, "2": 0}
        confidence_bins = {"high_correct": 0, "high_wrong": 0, "med_correct": 0, "med_wrong": 0, "low_correct": 0, "low_wrong": 0}
        proposals_count = {"1X2": 0, "GOLS": 0, "BTTS": 0, "PLACAR": 0}
        proposals_correct = {"1X2": 0, "GOLS": 0, "BTTS": 0, "PLACAR": 0}
        batch_kickoff = None
        pending_history: list[dict] = []

        def apply_pending() -> None:
            for pending in pending_history:
                hist.setdefault(pending["home_id"], deque(maxlen=window)).appendleft(pending["home"])
                hist.setdefault(pending["away_id"], deque(maxlen=window)).appendleft(pending["away"])

        for m in matches:
            kickoff = m["kickoff_datetime"]
            if batch_kickoff is not None and kickoff != batch_kickoff:
                apply_pending()
                pending_history.clear()
            batch_kickoff = kickoff
            hid, aid = m["home_team_id"], m["away_team_id"]
            hh = hist.get(hid)
            ah = hist.get(aid)
            if hh is not None and ah is not None and len(hh) > 0 and len(ah) > 0:
                home_l = compute_team_stats(hh, window, feature)
                away_l = compute_team_stats(ah, window, feature)
                mi = MatchInput(
                    home=TeamInput(name=m["home_name"], gf_avg=home_l.get("gf_avg", 0),
                                   ga_avg=home_l.get("ga_avg", 0)),
                    away=TeamInput(name=m["away_name"], gf_avg=away_l.get("gf_avg", 0),
                                   ga_avg=away_l.get("ga_avg", 0)),
                )
                result = run_predict(mi, home_advantage=home_adv, rho=rho)
                p = result.probs["1x2"]
                actual = "1" if m["score_home"] > m["score_away"] else (
                    "X" if m["score_home"] == m["score_away"] else "2")
                fav = max(p, key=p.get)
                hit = int(fav == actual)
                correct += hit
                wrong += (1 - hit)
                brier_sum += (1 - p[actual]) ** 2 + sum(p[k] ** 2 for k in p if k != actual)
                logloss_sum += -math.log(max(p[actual], 1e-10))
                total += 1
                series.append((total, correct / total * 100))

                # Análise de erros
                if hit == 0:
                    errors_by_type[actual] += 1

                # Análise de confiança
                fav_prob = p[fav]
                if fav_prob >= 0.6:
                    if hit:
                        confidence_bins["high_correct"] += 1
                    else:
                        confidence_bins["high_wrong"] += 1
                elif fav_prob >= 0.45:
                    if hit:
                        confidence_bins["med_correct"] += 1
                    else:
                        confidence_bins["med_wrong"] += 1
                else:
                    if hit:
                        confidence_bins["low_correct"] += 1
                    else:
                        confidence_bins["low_wrong"] += 1

                # Propostas do modelo (só gera se confiança > 55%)
                fav_prob = max(p.values())
                if fav_prob >= 0.55:
                    for prop in result.proposals:
                        prop_type = prop.get("tipo", "")
                        if prop_type in proposals_count:
                            # Filtra propostas por confiança mínima
                            conf = prop.get("confianca", 0)
                            if prop_type == "1X2" and conf < 55:
                                continue
                            proposals_count[prop_type] += 1
                            # Verifica se a proposta acertou
                            jogada = prop.get("jogada", "")
                            if prop_type == "1X2":
                                if "Back" in jogada:
                                    if (m["home_name"] in jogada and actual == "1") or \
                                       (m["away_name"] in jogada and actual == "2"):
                                        proposals_correct[prop_type] += 1
                                elif "Lay" in jogada and actual == "X":
                                    proposals_correct[prop_type] += 1
                            elif prop_type == "GOLS":
                                total_goals = m["score_home"] + m["score_away"]
                                if "Over 2.5" in jogada and total_goals > 2.5:
                                    proposals_correct[prop_type] += 1
                                elif "Under 2.5" in jogada and total_goals < 2.5:
                                    proposals_correct[prop_type] += 1
                                elif "Over 1.5" in jogada and total_goals > 1.5:
                                    proposals_correct[prop_type] += 1
                            elif prop_type == "BTTS":
                                both_scored = m["score_home"] >= 1 and m["score_away"] >= 1
                                if "BTTS Sim" in jogada and both_scored:
                                    proposals_correct[prop_type] += 1
                                elif "BTTS Nao" in jogada and not both_scored:
                                    proposals_correct[prop_type] += 1
                            elif prop_type == "PLACAR":
                                exact = f"{m['score_home']}-{m['score_away']}"
                                if exact in jogada:
                                    proposals_correct[prop_type] += 1

            # Hold outcomes until the whole simultaneous kickoff was evaluated.
            gm = compute_match_stats({
                "score_home": m["score_home"],
                "score_away": m["score_away"],
                "xg_home": m["xg_home"],
                "xg_away": m["xg_away"],
            }, feature)
            pending_history.append({
                "home_id": hid, "away_id": aid,
                "home": {"gf": gm["gf"], "ga": gm["ga"]},
                "away": {"gf": gm["ga"], "ga": gm["gf"]},
            })

        apply_pending()

        if total == 0:
            return {"accuracy": 0.0, "brier": 0.0, "logloss": 0.0,
                    "correct": 0, "wrong": 0, "total": 0,
                    "proposals": [], "error_analysis": {}, "series": []}

        # Amostra a cada ~5% dos jogos para uma curva suave (máx ~60 pontos)
        step = max(1, len(series) // 60)
        sampled = [{"n": n, "acc": round(acc, 1)} for i, (n, acc) in enumerate(series) if i % step == 0]
        if sampled and sampled[-1]["n"] != series[-1][0]:
            sampled.append({"n": series[-1][0], "acc": round(series[-1][1], 1)})

        # Calcula métricas de propostas
        proposal_metrics = {}
        for ptype in proposals_count:
            cnt = proposals_count[ptype]
            cor = proposals_correct[ptype]
            proposal_metrics[ptype] = {
                "total": cnt,
                "correct": cor,
                "accuracy": round(cor / cnt * 100, 1) if cnt > 0 else 0,
            }

        return {
            "accuracy": round(correct / total * 100, 2),
            "brier": round(brier_sum / total, 4),
            "logloss": round(logloss_sum / total, 4),
            "correct": correct,
            "wrong": wrong,
            "total": total,
            "series": sampled,
            "proposals": proposal_metrics,
            "error_analysis": {
                "errors_by_result": errors_by_type,
                "confidence_bins": confidence_bins,
                "total_errors": wrong,
                "error_rate": round(wrong / total * 100, 2),
            },
        }
    def _compare_with_previous(self, league_id: int, current: dict) -> dict:
        """Compara resultado atual com ciclo anterior para detectar evolução/volução."""
        # Pega último resultado desta liga do histórico
        if not os.path.exists(paths._HISTORY_FILE):
            return {"trend": "new", "delta_accuracy": 0, "delta_brier": 0}

        prev = None
        with open(paths._HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    cycle = json.loads(line)
                    for r in cycle.get("results", []):
                        if r.get("league_id") == league_id and not r.get("error"):
                            prev = r
                except json.JSONDecodeError:
                    continue

        if not prev or not prev.get("backtest"):
            return {"trend": "new", "delta_accuracy": 0, "delta_brier": 0}

        prev_bt = prev["backtest"]
        curr_bt = current
        delta_acc = round(curr_bt["accuracy"] - prev_bt.get("accuracy", 0), 2)
        delta_brier = round(curr_bt["brier"] - prev_bt.get("brier", 0), 4)

        if delta_acc > 0.5 or delta_brier < -0.005:
            trend = "evolution"
        elif delta_acc < -0.5 or delta_brier > 0.005:
            trend = "involution"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "delta_accuracy": delta_acc,
            "delta_brier": delta_brier,
            "previous_accuracy": prev_bt.get("accuracy"),
            "previous_brier": prev_bt.get("brier"),
        }
