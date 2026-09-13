"""Varredura de ligas candidatas para expansão progressiva (FASE 15).

Lê `update de ligas/ligas_sofascore.xlsx` (161 ligas) e ranqueia as mais
adequadas para entrar no AP2WEB — league-format apenas (sem copas/supercopas/
seleções/fragmentadas), priorizando divisões principais com cobertura robusta
de dados no Sofascore.

Saída: `app/data/league_scan.json` + tabela impressa, com:
  - recomendação por ONDA (1 = primeiro rollout, até o 4)
  - score heurístico estático (0-100) baseado em formato + região + nível
  - alerta: o GATE definitivo é empírico (cobertura de xG >= 80% após sync),
    porque no Sofascore isso varia muito por liga (BASE.md §36 Veracidade)

Uso: cd backend && .venv/bin/python -m scripts.scan_leagues
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

XLSX = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "update de ligas", "ligas_sofascore.xlsx")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "app", "data", "league_scan.json")

# --- Exclusão: formatos que NÃO geram dados úteis p/ calibração Poisson ---
EXCLUDE_KEYWORDS = (
    "cup", "copa", "coupe", "coppa", "pokal", "pokalen", "puchar", "kupa",
    "kubok", "supercup", "supercopa", "superpuchar", "supercoupe",
    "supercoppa", "supercupa", "superkubok", "shield", "super liga",
    "taça", "taca", "playoffs", "relegation", "nations league", "world cup",
    "olympics", "cupba", "nations", "european championship", "copa america",
    "frauen", "regionalliga", "knvb beker", "johan cruijff", "serie c",
    "girone", "souper kap", "supercopa de", "super kupa", "superkubok",
    "canadian championship", "fa community", "dfb-pokal", "greek cup",
    "russian cup", "russian super", "scottish cup", "schweizer pokal",
    "dbu pokalen", "suomen cup", "copa del rey", "copa mx", "oefb cup",
    "superliga", "champions league", "europa league", "conference league",
    "afc champions", "copa",
) + ("kupa",)

# Divisão principal de cada liga (nome → nível), para classificar 1ª vs resto
TOP_FLIGHT = {
    # Europa
    "austria - bundesliga", "greece - super league", "poland - exstraklasa",
    "czech republic - synot liga", "romania - liga i", "ukraine - premier liha",
    "russia - rfpl", "hungary - nb i", "bulgaria - a pfg",
    "israel - ligat ha'al", "slovenia - prvaliga", "iceland - urvalsdeild",
    "wales - welsh premier league", "northern ireland - premiership",
    "malta - premier league", "bosnia and herzegovina - premier liga",
    # Américas
    "bolivia - lfpb", "venezuela - primera división",
    "panama - liga panameña de fútbol", "argentina - primera b nacional",
    "brazil - série d",
    # Ásia / África / Oceania
    "australia - a league", "india - indian super league",
    "vietnam - v-league", "south africa - absa premiership",
    "india - i-league", "japan - j. league division 2",
}

SECOND_DIVISION = {
    "austria - liga zwa", "netherlands - eerste divisie",
    "sweden - superettan", "poland - division 1", "romania - liga ii",
    "russia - fnl", "scotland - championship", "turkey - 1. lig",
}

# Região → peso base de cobertura esperada no Sofascore (empírico aproximado)
REGION_WEIGHT = {
    "Europe": 90, "Americas": 85, "Asia": 80, "Africa": 78, "Oceania": 80,
    "World": 60, "Europe/Asia": 88,
}

COUNTRY_REGION = {
    "Austria": "Europe", "Greece": "Europe", "Poland": "Europe",
    "Czech Republic": "Europe", "Romania": "Europe", "Ukraine": "Europe",
    "Russia": "Europe", "Hungary": "Europe", "Bulgaria": "Europe",
    "Israel": "Europe", "Slovenia": "Europe", "Iceland": "Europe",
    "Wales": "Europe", "Northern Ireland": "Europe", "Malta": "Europe",
    "Bosnia and Herzegovina": "Europe", "Latvia": "Europe", "Lithuania": "Europe",
    "Scotland": "Europe", "Netherlands": "Europe", "Sweden": "Europe",
    "Turkey": "Europe", "Switzerland": "Europe",
    "Bolivia": "Americas", "Venezuela": "Americas", "Panama": "Americas",
    "Argentina": "Americas", "Brazil": "Americas", "Canada": "Americas",
    "India": "Asia", "Vietnam": "Asia", "South Africa": "Africa",
    "Australia": "Oceania", "Japan": "Asia",
}


def _wave_and_score(name: str, country: str) -> tuple[int, int]:
    """Onda de rollout (1→4) e score estático 0-100."""
    n = name.lower()
    region = COUNTRY_REGION.get(country, "Europe")
    base = REGION_WEIGHT.get(region, 75)
    small_league = country in ("Malta", "Latvia", "Lithuania", "Iceland",
                               "Northern Ireland", "Estonia", "Wales",
                               "Bosnia and Herzegovina", "Bulgaria")
    if n in TOP_FLIGHT:
        level = 10
        wave = 1 if region == "Europe" else 2
    elif n in SECOND_DIVISION:
        level = 0
        wave = 3
    else:
        level = -5
        wave = 4
    score = base + level + (-10 if small_league else 0)
    return wave, max(0, min(100, score))


def _configured() -> set[str]:
    """Nomes normalizados das ligas já configuradas (para não re-recomendar)."""
    from app.leagues_config import load_leagues
    cfg = load_leagues()
    return {c["name"].strip().lower() for c in cfg}


def main() -> None:
    xl = pd.read_excel(XLSX)
    configured = _configured()
    candidates = []
    for _, r in xl.iterrows():
        name = str(r["Nome da Liga"]).strip()
        sid = r["SofaScore ID"]
        no_id = str(sid).strip() == "?" or pd.isna(sid)
        if not no_id:
            continue  # tem ID Sofascore real → já é liga configurada (57)
        low = name.lower()
        if low in configured:
            continue  # já configurada — não é candidata
        if any(k in low for k in EXCLUDE_KEYWORDS):
            continue
        country = str(r["País"]).strip()
        wave, score = _wave_and_score(name, country)
        candidates.append({
            "name": name,
            "country": country,
            "division": str(r["Divisão"]).strip(),
            "need_id_lookup": no_id,
            "sofascore_id": None if no_id else int(sid),
            "wave": wave,
            "score": score,
            "top_flight": low in TOP_FLIGHT,
        })

    candidates.sort(key=lambda c: (c["wave"], -c["score"], c["name"]))
    data = {
        "generated_from": XLSX,
        "criteria": {
            "exclusions": "copas/supercopas/seleções/playoffs/frauen/regionalliga",
            "gate": "menor rodada agendada e cobertura xG >= 80% após sync (empírico)",
            "note": "score é heurístico estático; ID Sofascore precisa ser resolvido "
                    "para 94% dos candidatos (fonte football-data.org)",
        },
        "total_candidates": len(candidates),
        "per_wave": {str(w): sum(1 for c in candidates if c["wave"] == w)
                     for w in (1, 2, 3, 4)},
        "candidates": candidates,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Candidatos elegíveis (league-format): {len(candidates)}\n")
    for w in (1, 2, 3, 4):
        group = [c for c in candidates if c["wave"] == w]
        if not group:
            continue
        print(f"=== ONDA {w} ({len(group)}) ===")
        for c in group:
            star = "1ª Div" if c["top_flight"] else "     "
            print(f"  [{c['score']:>3}] {star} {c['name']}")
        print()
    print(f"Salvo em: {OUT}")


if __name__ == "__main__":
    main()