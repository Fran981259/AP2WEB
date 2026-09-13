"""Backtest Engine — ciclos síncronos consumidos pelo worker de jobs.

Componentes:
  1. TemporalCV: cross-validation temporal K-fold (zero leakage)
   2. MetaLearner: sugestões heurísticas baseadas no histórico
   3. BacktestLoop: execução de ciclo e leitura do histórico

Fluxo por ciclo:
  1. Para cada liga com dados suficientes:
     a. Roda walk-forward backtest (learning.backtest_league)
     b. Roda TemporalCV para validação robusta
     c. Alimenta MetaLearner com métricas
  2. MetaLearner sugere novos hiperparâmetros
  3. Roda calibrate_league com grid expandido
  4. Compara métricas antes/depois
  5. Promove ou reverte parâmetros
  6. Persiste resultado no evolution_tracker
"""
from __future__ import annotations

import json
import math
import os
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import db
from .feature_engine import compute_team_stats, compute_match_stats
from .learning import (
    backtest_league, calibrate_league, get_model,
    FEATURE_GRID, WINDOW_GRID, HOME_ADVANTAGE_GRID, RHO_GRID, MIN_SAMPLES,
)
from .model import MatchInput, TeamInput, predict as run_predict

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent / "data"
_HISTORY_FILE = _DATA_DIR / "backtest_history.jsonl"
_STATE_FILE = _DATA_DIR / "backtest_state.json"
_META_FILE = _DATA_DIR / "meta_learner.json"


# ---------------------------------------------------------------------------
# 1. TEMPORAL CROSS-VALIDATION
# ---------------------------------------------------------------------------
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

        # Testa nos jogos do fold
        for m in test_matches:
            hid, aid = m["home_team_id"], m["away_team_id"]
            hh = hist.get(hid)
            ah = hist.get(aid)
            if hh is not None and ah is not None and len(hh) > 0 and len(ah) > 0:
                home_l = compute_team_stats(hh, window, feature)
                away_l = compute_team_stats(ah, window, feature)
                mi = MatchInput(
                    home=TeamInput(name="h", gf_avg=home_l.get("gf_avg", 0),
                                   ga_avg=home_l.get("ga_avg", 0)),
                    away=TeamInput(name="a", gf_avg=away_l.get("gf_avg", 0),
                                   ga_avg=away_l.get("ga_avg", 0)),
                )
                p = run_predict(mi, home_advantage=home_adv, rho=rho).probs["1x2"]
                actual = "1" if m["score_home"] > m["score_away"] else (
                    "X" if m["score_home"] == m["score_away"] else "2")
                fav = max(p, key=p.get)
                hit = int(fav == actual)
                correct += hit
                brier_sum += (1 - p[actual]) ** 2 + sum(p[k] ** 2 for k in p if k != actual)
                total += 1

            # Adiciona ao histórico para o próximo fold
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


# ---------------------------------------------------------------------------
# 2. META-LEARNER (Bayesian Optimization)
# ---------------------------------------------------------------------------
class MetaLearner:
    """Aprende com histórico de backtests para sugerir melhores hiperparâmetros."""

    def __init__(self):
        self.history: list[dict] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(_META_FILE):
            try:
                with open(_META_FILE) as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []
        # Se não tem histórico no meta file, tenta reconstruir do histórico de ciclos
        if not self.history:
            self._rebuild_from_cycle_history()

    def _rebuild_from_cycle_history(self):
        """Reconstrói histórico do meta-learner a partir dos ciclos salvos."""
        if not os.path.exists(_HISTORY_FILE):
            return
        try:
            with open(_HISTORY_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    cycle = json.loads(line)
                    for result in cycle.get("results", []):
                        if result.get("error"):
                            continue
                        params = result.get("current_params", {})
                        bt = result.get("backtest", {})
                        cv = result.get("cv", {})
                        if params and bt:
                            self.history.append({
                                "league_id": result.get("league_id"),
                                "feature": params.get("feature", "xg"),
                                "window": params.get("window", 10),
                                "home_advantage": params.get("home_advantage", 1.15),
                                "rho": params.get("rho", 0.0),
                                "accuracy": bt.get("accuracy", 0),
                                "brier": bt.get("brier", 1.0),
                                "cv_mean_brier": cv.get("mean_brier"),
                                "timestamp": cycle.get("timestamp", ""),
                            })
            if self.history:
                self._save()
        except Exception:
            pass

    def _save(self):
        os.makedirs(os.path.dirname(_META_FILE), exist_ok=True)
        with open(_META_FILE, "w") as f:
            json.dump(self.history, f, indent=2)

    def record(self, league_id: int, params: dict, metrics: dict):
        """Registra resultado de um backtest."""
        with self._lock:
            self.history.append({
                "league_id": league_id,
                "feature": params.get("feature", "xg"),
                "window": params.get("window", 10),
                "home_advantage": params.get("home_advantage", 1.15),
                "rho": params.get("rho", 0.0),
                "accuracy": metrics.get("accuracy", 0),
                "brier": metrics.get("brier", 1.0),
                "cv_mean_brier": metrics.get("cv_mean_brier"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Mantém apenas últimos 500 registros
            if len(self.history) > 500:
                self.history = self.history[-500:]
            self._save()

    def suggest(self, league_id: int) -> list[dict]:
        """Sugestões heurísticas; não executa otimização bayesiana."""
        # Filtra histórico relevante (mesma liga ou global)
        relevant = [h for h in self.history if h.get("league_id") == league_id]
        if not relevant:
            relevant = self.history[-100:]  # usa global se não tem da liga

        if len(relevant) < 5:
            return self._grid_suggestions()

        return self._heuristic_suggestions(relevant)

    def _grid_suggestions(self) -> list[dict]:
        """Sugestões iniciais: grid coarse, mas já incorpora melhores resultados do histórico."""
        # Se tem histórico global, usa os melhores como base
        if self.history:
            best_sorted = sorted(self.history, key=lambda h: h.get("brier", 1.0))
            best_3 = best_sorted[:3]
            suggestions = []
            for b in best_3:
                # Variações do melhor já testado
                suggestions.append({
                    "feature": b["feature"],
                    "window": max(3, b["window"] - 2),
                    "home_advantage": b["home_advantage"],
                    "rho": b["rho"],
                })
                suggestions.append({
                    "feature": b["feature"],
                    "window": min(20, b["window"] + 2),
                    "home_advantage": b["home_advantage"],
                    "rho": b["rho"],
                })
                suggestions.append({
                    "feature": b["feature"],
                    "window": b["window"],
                    "home_advantage": round(b["home_advantage"] + 0.03, 4),
                    "rho": b["rho"],
                })
                suggestions.append({
                    "feature": b["feature"],
                    "window": b["window"],
                    "home_advantage": round(b["home_advantage"] - 0.03, 4),
                    "rho": b["rho"],
                })
                suggestions.append({
                    "feature": b["feature"],
                    "window": b["window"],
                    "home_advantage": b["home_advantage"],
                    "rho": round(b["rho"] - 0.03, 4),
                })
            # Remove duplicatas
            seen = set()
            unique = []
            for s in suggestions:
                key = (s["feature"], s["window"], s["home_advantage"], s["rho"])
                if key not in seen:
                    seen.add(key)
                    unique.append(s)
            return unique[:15]

        # Fallback: grid puro (sem histórico)
        suggestions = []
        for feature in FEATURE_GRID:
            for window in WINDOW_GRID:
                for ha in HOME_ADVANTAGE_GRID:
                    for rho in RHO_GRID:
                        suggestions.append({
                            "feature": feature,
                            "window": window,
                            "home_advantage": ha,
                            "rho": rho,
                        })
        return suggestions[:20]

    def _heuristic_suggestions(self, history: list[dict]) -> list[dict]:
        """Sugestões heurísticas baseadas no histórico."""
        # Encontra melhores parâmetros já testados
        best = min(history, key=lambda h: h.get("brier", 1.0))

        suggestions = [
            # Variação do melhor
            {**best, "window": max(3, best["window"] - 2)},
            {**best, "window": min(20, best["window"] + 2)},
            {**best, "home_advantage": round(best["home_advantage"] + 0.03, 4)},
            {**best, "home_advantage": round(best["home_advantage"] - 0.03, 4)},
            {**best, "rho": round(best["rho"] + 0.03, 4)},
            {**best, "rho": round(best["rho"] - 0.03, 4)},
            # Feature alternativa
            {**best, "feature": "goals" if best["feature"] == "xg" else "xg"},
            {**best, "feature": "blend"},
        ]

        # Remove duplicatas e limita
        seen = set()
        unique = []
        for s in suggestions:
            key = (s["feature"], s["window"], s["home_advantage"], s["rho"])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique[:10]


# ---------------------------------------------------------------------------
# 3. BACKTEST LOOP (Background)
# ---------------------------------------------------------------------------
class BacktestLoop:
    """Executa ciclos síncronos; agendamento e cancelamento pertencem aos jobs."""

    def __init__(self):
        self._lock = threading.Lock()
        self.state = {
            "running": False,
            "cycle_count": 0,
            "last_cycle_at": None,
            "current_league": "",
            "current_phase": "",
            "cycle_results": [],
            "interval_hours": 6,
            "auto_start": False,
        }
        self.meta = MetaLearner()
        self._load_state()

    def _load_state(self):
        if os.path.exists(_STATE_FILE):
            try:
                with open(_STATE_FILE) as f:
                    saved = json.load(f)
                    self.state.update({k: v for k, v in saved.items()
                                       if k in ("cycle_count", "last_cycle_at",
                                                 "interval_hours", "auto_start",
                                                 "cycle_results", "league_history")})
            except Exception:
                pass
        # Se não tem cycle_results no state, carrega do histórico
        if not self.state.get("cycle_results"):
            try:
                history = self.get_history(1)
                if history:
                    self.state["cycle_results"] = history[-1].get("results", [])
                    self.state["last_cycle_at"] = history[-1].get("timestamp")
            except Exception:
                pass

    def _save_state(self):
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        to_save = {k: v for k, v in self.state.items()
                   if k in ("cycle_count", "last_cycle_at",
                            "interval_hours", "auto_start",
                            "cycle_results", "league_history")}
        with open(_STATE_FILE, "w") as f:
            json.dump(to_save, f, indent=2)

    def record_league_result(self, league_id: int, params: dict, metrics: dict):
        """Registra resultado de uma liga para persistência."""
        with self._lock:
            # Atualiza cycle_results mantendo só as últimas 50 ligas
            if "league_history" not in self.state:
                self.state["league_history"] = []
            self.state["league_history"].append({
                "league_id": league_id,
                "params": params,
                "metrics": metrics,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if len(self.state["league_history"]) > 200:
                self.state["league_history"] = self.state["league_history"][-200:]
            self._save_state()

    def status(self) -> dict:
        """Retorna estado atual do loop."""
        with self._lock:
            return {
                **self.state,
                "meta_history_count": len(self.meta.history),
                "league_history_count": len(self.state.get("league_history", [])),
            }

    def _execute_cycle(self, league_ids: list[int] | None = None,
                       progress_cb=None) -> dict:
        """Executa um ciclo completo de backtest (síncrono).

        ``progress_cb(idx, total, league_id)`` is invoked per league so callers
        (the job worker) can report progress and detect cancellation.
        """
        cycle_start = datetime.now(timezone.utc).isoformat()
        results = []

        # 1. Pega ligas com dados suficientes
        if league_ids is None:
            rows = db.run_query(
                "SELECT l.id, l.name, "
                "(SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id "
                " AND m.status='played' AND m.score_home IS NOT NULL) AS played "
                "FROM leagues l ORDER BY l.name")
            eligible = [r for r in rows if r["played"] >= MIN_SAMPLES]
        else:
            eligible = [{"id": lid, "name": f"Liga {lid}", "played": 0} for lid in league_ids]

        total = len(eligible)

        for idx, lg in enumerate(eligible):
            lid = lg["id"]
            with self._lock:
                self.state["current_league"] = lg["name"]
                self.state["current_phase"] = f"backtest ({idx+1}/{total})"
            if progress_cb is not None:
                progress_cb(idx, total, lid)

            try:
                result = self._backtest_league_meta(lid)
                results.append(result)
            except Exception as e:
                results.append({
                    "league_id": lid,
                    "league_name": lg["name"],
                    "error": str(e)[:200],
                })

        # 2. Persiste resultados
        cycle_result = {
            "timestamp": cycle_start,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "leagues_processed": len(results),
            "results": results,
            "meta_suggestions": len(self.meta.history),
        }
        self._append_history(cycle_result)

        with self._lock:
            self.state["cycle_count"] += 1
            self.state["last_cycle_at"] = cycle_start
            self.state["cycle_results"] = results
            self.state["current_phase"] = "concluído"
            self.state["current_league"] = ""
        self._save_state()

        return cycle_result

    def _backtest_league_meta(self, league_id: int) -> dict:
        """Backtest de uma liga com meta-learning, propostas e análise de erros."""

        # 1. Pega modelo atual
        current_model = get_model(league_id)

        # 2. Roda backtest com parâmetros atuais (detalhado)
        bt_result = self._backtest_detailed(
            league_id,
            home_adv=current_model["home_advantage"],
            window=current_model["window"],
            feature=current_model["feature"],
            rho=current_model.get("rho", 0.0),
        )

        # 3. Roda CV temporal
        cv_current = temporal_cv(
            league_id,
            feature=current_model["feature"],
            window=current_model["window"],
            home_adv=current_model["home_advantage"],
            rho=current_model.get("rho", 0.0),
        )

        # 4. Registra no meta-learner
        self.meta.record(league_id, current_model, {
            "accuracy": bt_result["accuracy"],
            "brier": bt_result["brier"],
            "cv_mean_brier": cv_current["mean_brier"],
        })

        # 5. Pega sugestões do meta-learner
        suggestions = self.meta.suggest(league_id)

        # 6. Testa melhores sugestões (até 3)
        best_new = None
        best_new_brier = bt_result["brier"]

        for s in suggestions[:3]:
            try:
                bt_s = backtest_league(
                    league_id,
                    home_adv=s["home_advantage"],
                    window=s["window"],
                    feature=s["feature"],
                    rho=s["rho"],
                )
                if bt_s["total"] >= MIN_SAMPLES and bt_s["brier"] < best_new_brier:
                    best_new = s
                    best_new_brier = bt_s["brier"]
            except Exception:
                continue

        # 7. Promove novos parâmetros se melhoraram
        promoted = False
        if best_new and best_new_brier < bt_result["brier"] - 0.001:
            try:
                calibrate_result = calibrate_league(league_id)
                promoted = calibrate_result is not None
            except Exception:
                pass

        # 8. Compara com ciclo anterior (evolução/volução)
        evolution = self._compare_with_previous(league_id, bt_result)

        return {
            "league_id": league_id,
            "league_name": db.run_query(
                "SELECT name FROM leagues WHERE id=?", (league_id,)
            )[0]["name"] if db.run_query("SELECT name FROM leagues WHERE id=?", (league_id,)) else f"Liga {league_id}",
            "current_params": {
                "feature": current_model["feature"],
                "window": current_model["window"],
                "home_advantage": current_model["home_advantage"],
                "rho": current_model.get("rho", 0.0),
            },
            "backtest": {
                "accuracy": bt_result["accuracy"],
                "brier": bt_result["brier"],
                "total": bt_result["total"],
                "correct": bt_result["correct"],
                "wrong": bt_result["wrong"],
            },
            "cv": {
                "mean_accuracy": cv_current["mean_accuracy"],
                "mean_brier": cv_current["mean_brier"],
                "std_accuracy": cv_current["std_accuracy"],
                "std_brier": cv_current["std_brier"],
                "n_folds": cv_current["n_folds"],
            },
            "proposals": bt_result.get("proposals", []),
            "error_analysis": bt_result.get("error_analysis", {}),
            "evolution": evolution,
            "meta_suggestion": best_new,
            "promoted": promoted,
            "improvement": round(bt_result["brier"] - best_new_brier, 4) if best_new else 0,
        }

    def _backtest_detailed(self, league_id: int, home_adv: float = 1.15,
                           window: int = 10, feature: str = "xg",
                           rho: float = 0.0) -> dict:
        """Backtest detalhado com análise de erros e propostas."""
        from .model import MatchInput, TeamInput, predict as run_predict

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

        for m in matches:
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

            # Usar Feature Engine para stats da partida (unificado com prediction.py)
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
        if not os.path.exists(_HISTORY_FILE):
            return {"trend": "new", "delta_accuracy": 0, "delta_brier": 0}

        prev = None
        with open(_HISTORY_FILE) as f:
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

    def get_summary(self) -> dict:
        """Retorna resumo geral de todas as ligas com evolução/volução."""
        results = self.state.get("cycle_results", [])
        if not results:
            return {"leagues": [], "overall": {}, "proposals_summary": {}}

        leagues = []
        total_correct = 0
        total_wrong = 0
        total_brier = 0.0
        proposals_summary = {"1X2": {"total": 0, "correct": 0},
                             "GOLS": {"total": 0, "correct": 0},
                             "BTTS": {"total": 0, "correct": 0},
                             "PLACAR": {"total": 0, "correct": 0}}

        for r in results:
            if r.get("error"):
                continue
            bt = r.get("backtest", {})
            evo = r.get("evolution", {})
            proposals = r.get("proposals", {})

            total_correct += bt.get("correct", 0)
            total_wrong += bt.get("wrong", 0)
            total_brier += bt.get("brier", 0) * bt.get("total", 0)

            # Acumula propostas
            for ptype in proposals:
                if ptype in proposals_summary:
                    proposals_summary[ptype]["total"] += proposals[ptype].get("total", 0)
                    proposals_summary[ptype]["correct"] += proposals[ptype].get("correct", 0)

            leagues.append({
                "league_id": r["league_id"],
                "league_name": r["league_name"],
                "accuracy": bt.get("accuracy", 0),
                "brier": bt.get("brier", 0),
                "correct": bt.get("correct", 0),
                "wrong": bt.get("wrong", 0),
                "total": bt.get("total", 0),
                "trend": evo.get("trend", "new"),
                "delta_accuracy": evo.get("delta_accuracy", 0),
                "delta_brier": evo.get("delta_brier", 0),
                "proposals": proposals,
                "promoted": r.get("promoted", False),
            })

        total_matches = total_correct + total_wrong
        overall_accuracy = round(total_correct / total_matches * 100, 2) if total_matches > 0 else 0
        overall_brier = round(total_brier / total_matches, 4) if total_matches > 0 else 0

        # Calcula accuracy das propostas
        for ptype in proposals_summary:
            p = proposals_summary[ptype]
            p["accuracy"] = round(p["correct"] / p["total"] * 100, 1) if p["total"] > 0 else 0

        return {
            "leagues": sorted(leagues, key=lambda x: x["accuracy"], reverse=True),
            "overall": {
                "accuracy": overall_accuracy,
                "brier": overall_brier,
                "correct": total_correct,
                "wrong": total_wrong,
                "total": total_matches,
                "leagues_count": len(leagues),
                "evolved": sum(1 for lg in leagues if lg["trend"] == "evolution"),
                "involved": sum(1 for lg in leagues if lg["trend"] == "involution"),
                "stable": sum(1 for lg in leagues if lg["trend"] == "stable"),
            },
            "proposals_summary": proposals_summary,
        }

    def _append_history(self, cycle_result: dict):
        """Registra ciclo no histórico (append-only)."""
        os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
        with open(_HISTORY_FILE, "a") as f:
            f.write(json.dumps(cycle_result) + "\n")

    def get_history(self, limit: int = 20) -> list[dict]:
        """Retorna últimos ciclos de backtest."""
        if not os.path.exists(_HISTORY_FILE):
            return []
        rows = []
        with open(_HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows[-limit:]


# ---------------------------------------------------------------------------
# Instância global
# ---------------------------------------------------------------------------
_loop: Optional[BacktestLoop] = None


def get_loop() -> BacktestLoop:
    """Retorna instância singleton do BacktestLoop."""
    global _loop
    if _loop is None:
        _loop = BacktestLoop()
    return _loop
