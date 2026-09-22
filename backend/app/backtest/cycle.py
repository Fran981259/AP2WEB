"""BacktestLoop cycle mixin: per-league meta-learning execution loop."""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db, execution_store
from ..learning import MIN_SAMPLES, backtest_league, calibrate_league, get_model
from .executions import _finish_execution, _snapshot_metadata
from .temporal import temporal_cv


class LoopCycleMixin:
    """Owns _execute_cycle and _backtest_league_meta."""


    def _execute_cycle(self, league_ids: list[int] | None = None, progress_cb=None,
                       source_job_id: int | None = None) -> dict:
        """Executa um ciclo completo de backtest (síncrono).

        ``progress_cb(idx, total, league_id)`` is invoked per league so callers
        (the job worker) can report progress and detect cancellation.
        """
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

        _manifest, snapshot = _snapshot_metadata(None)
        effective_parameters = {}
        for league in eligible:
            model = get_model(league["id"])
            effective_parameters[str(league["id"])] = {
                "home_advantage": model["home_advantage"],
                "window": model["window"],
                "feature": model["feature"],
                "rho": model.get("rho", 0.0),
            }
        parameters = {
            "scope": "cycle",
            "league_ids": [league["id"] for league in eligible],
            "effective_parameters": effective_parameters,
        }
        if source_job_id is not None:
            parameters["source_job_id"] = source_job_id
        execution = execution_store.start(
            execution_type="backtest", snapshot_hash=snapshot["hash"], parameters=parameters)

        cycle_start = datetime.now(timezone.utc).isoformat()
        results = []
        total = len(eligible)
        try:
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
                except Exception as error:
                    results.append({
                        "league_id": lid,
                        "league_name": lg["name"],
                        "error": str(error)[:200],
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
        except Exception as error:
            _finish_execution(execution["execution_id"], "failed", {
                "snapshot_manifest": snapshot,
                "error": str(error)[:2000],
            })
            raise

        _finish_execution(execution["execution_id"], "completed", {
            "snapshot_manifest": snapshot,
            "metrics": {
                "leagues_processed": cycle_result["leagues_processed"],
                "leagues_failed": sum("error" in result for result in results),
            },
            "results": cycle_result,
        })
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
