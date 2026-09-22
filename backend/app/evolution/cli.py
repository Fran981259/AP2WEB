"""CLI entry point: --baseline snapshot or --check comparison."""
from __future__ import annotations

import sys

from . import paths
from .analysis import _compare
from .executions import _finish_measurement_execution, _start_measurement_execution
from .history import _append_history, _load_baseline, _save_baseline
from .measure import _snapshot


def main():
    if "--baseline" in sys.argv:
        execution = _start_measurement_execution(skip_regression=False, source="cli_baseline")
        try:
            snap = _snapshot()
            _save_baseline(snap)
            _append_history(snap)
        except Exception as error:
            _finish_measurement_execution(execution, "failed", error=str(error)[:2000])
            raise
        _finish_measurement_execution(execution, "completed", snapshot=snap,
                                      results={"baseline_updated": True})
        print(f"Baseline salvo em {paths.BASELINE_FILE} ({snap['timestamp']})")
        return

    baseline = _load_baseline()
    if not baseline:
        print("Nenhum baseline. Rode com --baseline primeiro.")
        sys.exit(1)

    execution = _start_measurement_execution(skip_regression=False, source="cli_check")
    try:
        current = _snapshot()
        changes = _compare(current, baseline)

        if not changes:
            print("✅ Nenhuma evolução detectada — sistema está estável.")
        else:
            print(f"⚡ {len(changes)} mudança(s) detectada(s):")
            for c in changes:
                print(f"  {c['metric']}: {c['before']} → {c['after']} (delta={c['delta']})")

        # Persiste a medição no histórico e atualiza o baseline
        _append_history(current)
        _save_baseline(current)
    except Exception as error:
        _finish_measurement_execution(execution, "failed", error=str(error)[:2000])
        raise
    _finish_measurement_execution(execution, "completed", snapshot=current,
                                  results={"changes": changes, "baseline_updated": True})
