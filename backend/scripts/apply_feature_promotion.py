"""Aplicação de promoção FASE 14 — define features contextuais ativas por liga.

Lê `data/feature_experiment.json` e re-julga a promoção com o mesmo critério
rígido da FASE 13 (BASE.md §36): ganho >= 0.005 em Brier E LogLoss.

Grava em league_models:
  ctx_rest     INTEGER DEFAULT 0   (1 = aplicar fadiga)
  ctx_form     INTEGER DEFAULT 0   (1 = aplicar momentum)
  ctx_team_ha  INTEGER DEFAULT 0   (1 = aplicar mando próprio do time)

Variant→flags: rest=(1,0,0) form=(0,1,0) team_ha=(0,0,1) all=(1,1,1)

Uso:
  cd backend && .venv/bin/python -m scripts.apply_feature_promotion
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db  # noqa: E402

MIN_BRIER_GAIN = 0.005
MIN_LOGLOSS_GAIN = 0.005

VARIANTS_FLAGS = {
    "rest": (1, 0, 0),
    "form": (0, 1, 0),
    "team_ha": (0, 0, 1),
    "all": (1, 1, 1),
}

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "app", "data", "feature_experiment.json")


def _ensure_columns() -> None:
    cols = [r["name"] for r in db.run_query("PRAGMA table_info(league_models)")]
    for c in ("ctx_rest", "ctx_form", "ctx_team_ha"):
        if c not in cols:
            db.run_exec(f"ALTER TABLE league_models ADD COLUMN {c} INTEGER DEFAULT 0")


def main() -> None:
    _ensure_columns()
    with open(DATA_FILE, encoding="utf-8") as f:
        summary = json.load(f)

    applied = 0
    kept = 0
    for exp in summary["experiments"]:
        if exp.get("skipped"):
            continue
        lid = exp["league_id"]
        base = exp["models"]["base"]
        best = exp["best_variant"]
        if best == "base":
            db.run_exec("UPDATE league_models SET ctx_rest=0, ctx_form=0, ctx_team_ha=0 WHERE league_id=?",
                         (lid,))
            kept += 1
            continue
        gain_brier = base["brier"] - exp["models"][best]["brier"]
        gain_logloss = base["logloss"] - exp["models"][best]["logloss"]
        if gain_brier >= MIN_BRIER_GAIN and gain_logloss >= MIN_LOGLOSS_GAIN:
            r, f, t = VARIANTS_FLAGS[best]
            db.run_exec(
                "UPDATE league_models SET ctx_rest=?, ctx_form=?, ctx_team_ha=? WHERE league_id=?",
                (r, f, t, lid))
            applied += 1
            print(f"[PROMO] liga {lid}: {best} (brier {gain_brier:+.4f} / logloss {gain_logloss:+.4f})")
        else:
            db.run_exec("UPDATE league_models SET ctx_rest=0, ctx_form=0, ctx_team_ha=0 WHERE league_id=?",
                         (lid,))
            kept += 1
            print(f"[----] liga {lid}: {best} sem margem suficiente "
                  f"(brier {gain_brier:+.4f} / logloss {gain_logloss:+.4f})")

    rows = db.run_query("SELECT league_id, ctx_rest, ctx_form, ctx_team_ha "
                        "FROM league_models ORDER BY league_id")
    promos = [r for r in rows if r["ctx_rest"] or r["ctx_form"] or r["ctx_team_ha"]]
    print(f"\nPromovidas: {len(promos)} | Mantidas base (sem features): {kept}")
    for r in promos:
        flags = "".join(f"{k}={v}" for k, v in
                        (("rest", r["ctx_rest"]), ("form", r["ctx_form"]), ("ha", r["ctx_team_ha"])))
        print(f"  liga {r['league_id']}: {flags}")


if __name__ == "__main__":
    main()