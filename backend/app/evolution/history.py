"""Baseline and append-only history persistence."""
from __future__ import annotations

import json
import os

from . import paths


def _load_baseline() -> dict | None:
    if not os.path.exists(paths.BASELINE_FILE):
        return None
    with open(paths.BASELINE_FILE) as f:
        return json.load(f)
def _save_baseline(snap: dict):
    os.makedirs(os.path.dirname(paths.BASELINE_FILE), exist_ok=True)
    with open(paths.BASELINE_FILE, "w") as f:
        json.dump(snap, f, indent=2)
def _append_history(snap: dict):
    """Registro append-only: cada medição vira uma linha — nunca sobrescreve."""
    os.makedirs(os.path.dirname(paths.HISTORY_FILE), exist_ok=True)
    with open(paths.HISTORY_FILE, "a") as f:
        f.write(json.dumps(snap) + "\n")
def _load_history(limit: int = 50) -> list[dict]:
    """Histórico cronológico de medições (mais recente por último)."""
    if not os.path.exists(paths.HISTORY_FILE):
        return []
    rows = []
    with open(paths.HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # linha corrompida não derruba o histórico
    return rows[-limit:]
def _history_count() -> int:
    """Total de medições persistentes."""
    return len(_load_history(limit=10**9))
