"""BacktestLoop state mixin: init, JSON state, history file and summary."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

from . import paths
from .meta import MetaLearner


class LoopStateMixin:
    """Owns BacktestLoop.__init__, state persistence, history and summary."""


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
        if os.path.exists(paths._STATE_FILE):
            try:
                with open(paths._STATE_FILE) as f:
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
        os.makedirs(os.path.dirname(paths._STATE_FILE), exist_ok=True)
        to_save = {k: v for k, v in self.state.items()
                   if k in ("cycle_count", "last_cycle_at",
                            "interval_hours", "auto_start",
                            "cycle_results", "league_history")}
        with open(paths._STATE_FILE, "w") as f:
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
        os.makedirs(os.path.dirname(paths._HISTORY_FILE), exist_ok=True)
        with open(paths._HISTORY_FILE, "a") as f:
            f.write(json.dumps(cycle_result) + "\n")

    def get_history(self, limit: int = 20) -> list[dict]:
        """Retorna últimos ciclos de backtest."""
        if not os.path.exists(paths._HISTORY_FILE):
            return []
        rows = []
        with open(paths._HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows[-limit:]
