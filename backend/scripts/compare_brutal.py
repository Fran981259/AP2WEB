"""Compara passadas do backtest brutal (as-deployed vs honest) e a base MLE.

Produz console + JSON com:
  - por liga: produção (deployed/honest) vs base (poisson MLE calibrado)
  - vencedores por métrica (acc/brier/logloss) por método
  - overall ponderado
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]  # repo root


def load(name: str) -> list:
    p = Path(BASE) / "backend" / "app" / "data" / name
    return json.loads(p.read_text())["leagues"]


def main() -> None:
    deployed = {r["league_id"]: r for r in load("brutal_backtest_asdeployed.json")}
    honest = {r["league_id"]: r for r in load("brutal_backtest_honest.json")}
    keys = sorted(set(deployed) & set(honest))

    rows = []
    for k in keys:
        d, h = deployed[k], honest[k]
        base_b = d["base"]["brier"]
        prod_d, prod_h = d["production"], h["production"]
        rows.append({
            "id": k, "name": h["name"], "method": h["method"],
            "ctx": h["context"], "n": prod_h["total"],
            "acc_d": prod_d.get("accuracy"), "acc_h": prod_h.get("accuracy"),
            "brier_d": prod_d.get("brier"), "brier_h": prod_h.get("brier"),
            "ll_d": prod_d.get("logloss"), "ll_h": prod_h.get("logloss"),
            "ece_d": prod_d.get("ece"), "ece_h": prod_h.get("ece"),
            "brier_base": base_b,
        })

    def s(x, nd=4):
        return "—" if x is None else f"{x:.{nd}f}"

    print(f"{'Liga':42} {'método':10} {'n':>4} | {'deploy brier':>12} {'honest brier':>12} {'base MLE':>8} {'Δhon-vs-depl':>12} {'ece_h':>6} {'acc_h':>7}")
    w_d, w_h = 0, 0
    tb_d = tb_h = tb_base = 0.0
    tn = 0
    for r in rows:
        hb, bb, db = r["brier_h"], r["brier_base"], r["brier_d"]
        gains = ""
        if r["method"] != "poisson":
            tags = []
            if hb is not None and hb < bb:
                tags.append("✔>base")
            if db is not None and hb is not None:
                tags.append("h<d" if hb < db else ("h>d" if hb > db else "="))
            gains = " ".join(tags)
        tb_d += (db or 0) * r["n"]; tb_h += (hb or 0) * r["n"]; tb_base += bb * r["n"]; tn += r["n"]
        if db is not None and hb is not None:
            w_d += (db < bb); w_h += (hb < bb)
        print(f"{r['name'][:42]:42} {r['method']:10} {r['n']:>4} | {s(db):>12} {s(hb):>12} {s(bb):>8} {s((hb-db) if (hb is not None and db is not None) else None):>12} {s(r['ece_h'],3):>6} {s(r['acc_h'],2):>7}  {gains}")

    print("\n--- OVERALL (ponderado por n) ---")
    print(f"deployed brier: {tb_d/tn:.4f}  honest brier: {tb_h/tn:.4f}  base MLE: {tb_base/tn:.4f}")
    print(f"ligas onde deployed<base: {w_d}/{len(rows)}   honest<base: {w_h}/{len(rows)}")
    by = {}
    for r in rows:
        by.setdefault(r["method"], {"n": 0, "b_h": 0.0, "b_d": 0.0, "b_base": 0.0, "c": 0})
        g = by[r["method"]]
        g["n"] += r["n"]; g["b_h"] += (r["brier_h"] or 0) * r["n"]; g["b_d"] += (r["brier_d"] or 0) * r["n"]; g["b_base"] += r["brier_base"] * r["n"]; g["c"] += 1
    for m, g in sorted(by.items()):
        print(f"  {m:8} ligas={g['c']:>2} n={g['n']:>5}  deployed={g['b_d']/g['n']:.4f}  honest={g['b_h']/g['n']:.4f}  base={g['b_base']/g['n']:.4f}")

    print("\n--- TOP 8 PIORES ECE (calibração) — honest ---")
    for r in sorted(rows, key=lambda x: x["ece_h"] or 9, reverse=True)[:8]:
        print(f"  {r['name'][:40]:40} ece={r['ece_h']} acc={r['acc_h']}% n={r['n']}")

    print("\n--- TOP 8 MELHORES Brier HONEST vs BASE (ganho) ---")
    for r in sorted([x for x in rows if x["brier_h"] and x["brier_base"]], key=lambda x: x["brier_base"] - x["brier_h"], reverse=True)[:8]:
        print(f"  {r['name'][:40]:40} ganho={r['brier_base']-r['brier_h']:+.4f}  honest={r['brier_h']} base={r['brier_base']}")

    out = Path("/tmp/opencode/bt_compare.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"\ndetalhe em {out}")


if __name__ == "__main__":
    main()