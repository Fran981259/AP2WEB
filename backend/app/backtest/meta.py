"""MetaLearner: heuristic hyperparameter suggestions from cycle history."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

from ..learning import (
    FEATURE_GRID,
    HOME_ADVANTAGE_GRID,
    RHO_GRID,
    WINDOW_GRID,
)
from . import paths


class MetaLearner:
    """Aprende com histórico de backtests para sugerir melhores hiperparâmetros."""

    def __init__(self):
        self.history: list[dict] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(paths._META_FILE):
            try:
                with open(paths._META_FILE) as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []
        # Se não tem histórico no meta file, tenta reconstruir do histórico de ciclos
        if not self.history:
            self._rebuild_from_cycle_history()

    def _rebuild_from_cycle_history(self):
        """Reconstrói histórico do meta-learner a partir dos ciclos salvos."""
        if not os.path.exists(paths._HISTORY_FILE):
            return
        try:
            with open(paths._HISTORY_FILE) as f:
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
        os.makedirs(os.path.dirname(paths._META_FILE), exist_ok=True)
        with open(paths._META_FILE, "w") as f:
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
