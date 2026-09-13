"""Aplica decisão de promoção do Bayesian Engine por liga (FASE 13).

Lê o resultado do experimento walk-forward (data/bayesian_experiment.json)
e, para cada liga com evidência de que Bayesian/híbrido supera MLE, atualiza
league_models.bayesian = 1 e league_models.method.

Critério de promoção (evidência por liga):
  - brier_B < brier_A E logloss_B < logloss_A  → method = 'bayesian'
  - senão se brier_C < brier_A E logloss_C < logloss_A → method = 'hybrid'
  - senão → mantém 'poisson' (MLE continua melhor)

Nunca promove sem evidência mensurável (BASE.md §36 Veracidade).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db  # noqa: E402

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "app", "data", "bayesian_experiment.json")


def _better(b_x: dict, a_y: dict, brier_gain: float = 0.005,
            logloss_gain: float = 0.005) -> bool:
    """Retorna True se (brier, logloss) melhor que (accuracy) com ganho mínimo.

    Melhor = menor brier E menor logloss, com margem >= ganho.
    """
    if b_x["brier"] >= a_y["brier"] - brier_gain:
        return False
    if b_x["logloss"] >= a_y["logloss"] - logloss_gain:
        return False
    return True


def main() -> None:
    if not os.path.exists(DATA_FILE):
        print(f"ERRO: {DATA_FILE} não encontrado. Rode scripts.bayesian_experiment primeiro.")
        sys.exit(1)

    data = json.load(open(DATA_FILE, encoding="utf-8"))
    exps = [e for e in data["experiments"] if not e.get("skipped")]

    promoted, kept, errors = [], [], []

    for e in exps:
        lid = e["league_id"]
        a = e["models"]["A_mle"]
        b = e["models"]["B_bayesian"]
        c = e["models"]["C_hybrid"]

        # Importa _ensure_bayesian_columns
        from app.learning import _ensure_bayesian_columns
        _ensure_bayesian_columns()

        if _better(b, a):
            method, bayesian = "bayesian", 1
        elif _better(c, a):
            method, bayesian = "hybrid", 1
        else:
            method, bayesian = "poisson", 0

        db.run_exec(
            "UPDATE league_models SET bayesian=?, method=? WHERE league_id=?",
            (bayesian, method, lid))
        if bayesian:
            promoted.append((lid, method))
        else:
            kept.append(lid)

    print(f"=== Promoção FASE 13 ===")
    print(f"Promovidas para Bayesian/Híbrido: {len(promoted)}")
    for lid, m in sorted(promoted):
        print(f"  liga {lid}: method={m}")
    print(f"Mantidas como Poisson (MLE melhor): {len(kept)}: {sorted(kept)}")
    print(f"Total avaliado: {len(exps)}")


if __name__ == "__main__":
    main()