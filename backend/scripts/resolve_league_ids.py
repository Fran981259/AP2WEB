"""Resolve IDs de unique-tournament no Sofascore para as ligas candidatas (FASE 15).

Para cada candidato em `app/data/league_scan.json`, consulta a API de busca do
Sofascore (mesmo mecanismo TLS do sync) e associa o melhor uniqueTournament.
Não grava nada no banco/config: o resultado é para REVISÃO HUMANA antes de
entrar na config (BASE.md §36 — nunca inventar IDs).

- Saída: `app/data/league_ids.json` (status: resolved / review / not_found)
- Cache local em `app/data/.search_cache.json` para não repetir requisições
- 1 requisição por liga + sleep 1.5s (rate-limit do Sofascore ~5-13 requests)

Uso: cd backend && .venv/bin/python -m scripts.resolve_league_ids [--wave 1]
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import unicodedata
import urllib.parse
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.sofascore_data import _client  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "app", "data")
PATH_SCAN = os.path.join(DATA, "league_scan.json")
PATH_OUT = os.path.join(DATA, "league_ids.json")
PATH_CACHE = os.path.join(DATA, ".search_cache.json")

# Consultas mais reconhecíveis para o Sofascore que o nome do XLSX (opcional)
QUERY_OVERRIDE = {
    "austria - bundesliga": "Austrian Bundesliga",
    "czech republic - synot liga": "Czech Liga",
    "greece - super league": "Greece Super League",
    "hungary - nb i": "NB I",
    "israel - ligat ha'al": "Ligat ha'Al",
    "poland - exstraklasa": "Ekstraklasa",
    "romania - liga i": "Liga I",
    "russia - rfpl": "RFPL Premier League",
    "slovenia - prvaliga": "PrvaLiga",
    "ukraine - premier liha": "Premier League Ukraine",
    "bosnia and herzegovina - premier liga": "Premier Liga BiH",
    "bulgaria - a pfg": "Parva Liga",
    "malta - premier league": "Maltese Premier League",
    "northern ireland - premiership": "NIFL Premiership",
    "wales - welsh premier league": "Welsh Premier League",
    "argentina - primera b nacional": "Primera B Nacional",
    "brazil - série d": "Serie D Brazil",
    "japan - j. league division 2": "J.League Division 2",
    "turkey - 1. lig": "1. Lig",
    "scotland - championship": "Scottish Championship",
    "netherlands - eerste divisie": "Eerste Divisie",
    "south africa - absa premiership": "Premier Soccer League",
    "india - indian super league": "Indian Super League",
    "india - i-league": "I-League",
    "iceland - úrvalsdeild": "Urvalsdeild",
    "latvia - virslīga": "Virslīga",
    "lithuania - a lyga": "A Lyga",
}

# Consultas CURADAS para os casos que o primeiro passe resolveu errado
# (esporte diferente, país errado, nome que o Sofascore mudou) — re-consultadas
# em --verify e conferidas por detalhe (sport=football + país correto).
CURATED_QUERY = {
    "czech republic - synot liga": "Czech First League",
    "greece - super league": "Super League Greece",
    "israel - ligat ha'al": "Israeli Premier League",
    "romania - liga i": "Romania SuperLiga",
    "russia - rfpl": "Russian Premier League",
    "malta - premier league": "Premier League Malta",
    "wales - welsh premier league": "Cymru Premier",
    "bolivia - lfpb": "Bolivia Primera Division",
    "venezuela - primera división": "Liga FUTVE",
    "panama - liga panameña de fútbol": "Liga Panameña de Fútbol",
    "australia - a league": "A-League Men",
    "india - i-league": "I-League football",
    "japan - j. league division 2": "J2 League",
    "vietnam - v-league": "V.League 1",
    "netherlands - eerste divisie": "Eerste Divisie Netherlands",
    "russia - fnl": "Pervaya Liga Russia",
    "poland - division 1": "I liga Poland",
    "austria - liga zwa": "2. Liga Austria",
    "romania - liga ii": "Liga 2 Romania",
    "lithuania - a lyga": "Lithuania A Lyga",
    "hungary - nb i": "OTP Bank Liga",
    "bosnia and herzegovina - premier liga": "Bosnian Premier League",
    "turkey - 1. lig": "TFF 1.Lig",
    "south africa - absa premiership": "South African Premier Division",
}

# Correspondências confirmadas manualmente após revisão humana
# (cada id verificado via details: sport=Football + país correto)
CONFIRMED = {
    "austria - bundesliga": 45,
    # Onda 2 (FASE 15, verificadas 2026-08-29)
    "argentina - primera b nacional": 703,
    "bolivia - lfpb": 16736,
    "brazil - série d": 10326,
    "india - indian super league": 1900,
    "india - i-league": 848,
    "vietnam - v-league": 626,
    "panama - liga panameña de fútbol": 11533,
    "venezuela - primera división": 231,
    "australia - a league": 136,
    "japan - j. league division 2": 402,
    "south africa - absa premiership": 358,
    # Onda 3 (FASE 15, verificadas 2026-08-29)
    "austria - liga zwa": 135,
    "netherlands - eerste divisie": 131,
    "poland - division 1": 229,
    "romania - liga ii": 562,
    "russia - fnl": 204,
    "scotland - championship": 206,
    "sweden - superettan": 46,
    "turkey - 1. lig": 98,
    # Onda 4 (FASE 15, verificadas 2026-08-29)
    "iceland - úrvalsdeild": 188,
    "latvia - virslīga": 197,
}

# Ligas que exigem ID manual: a busca do Sofascore não retorna o time principal
FORCE_REVIEW = {
    "bosnia and herzegovina - premier liga": "só Juniori/feminino/futsal na busca; ID do masculino manual",
    "lithuania - a lyga": "id 9460 (Úrvalsdeild) é HANDEBOL; A Lyga masculina ausente na busca (só Women 25410/futsal/amadores). Não usar.",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c.lower() for c in text if c.isalnum() or c.isspace())


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _search(query: str, cache: dict) -> list[dict]:
    if query in cache:
        return cache[query]
    url = "https://www.sofascore.com/api/v1/search/all?q=" + urllib.parse.quote(query)
    data = json.load(_client().get(url))
    hits = []
    for r in data.get("results", []):
        if r.get("type") != "uniqueTournament":
            continue
        e = r.get("entity", {}) or {}
        hits.append({"name": e.get("name"), "id": e.get("id"),
                     "country": (e.get("country") or {}).get("name")})
    cache[query] = hits
    return hits


def _details(tid: int, cache: dict) -> dict:
    """Detalhe do unique-tournament: confirma sport=Football e país (nó category)."""
    key = f"details:{tid}"
    if key in cache:
        return cache[key]
    url = f"https://www.sofascore.com/api/v1/unique-tournament/{tid}"
    data = json.load(_client().get(url))
    ut = data.get("uniqueTournament", {}) or {}
    cat = ut.get("category") or {}
    out = {"name": ut.get("name"),
           "sport": (cat.get("sport") or {}).get("name"),
           "country": (cat.get("country") or {}).get("name"),
           "category": cat.get("name")}
    cache[key] = out
    return out


_CUP_TERMS = ("cup", "kupa", "pokal", "supercopa", "shield", "souper", "coppa", "coupe")
_YOUTH_TERMS = ("juniori", "juniors", "u19", "u20", "u21", "sub-", "women",
                "frauen", "zenska", "womens", "reserve")
# Alias de países usados pelo Sofascore vs nomes do catálogo (XLSX)
COUNTRY_ALIAS = {
    "Czech Republic": "Czechia",
    "Bosnia and Herzegovina": "Bosnia",
    "South Africa": "South Africa",
    "Northern Ireland": "Northern Ireland",
    "Macedonia": "North Macedonia",
    "South Korea": "Korea",
    "Turkey": "Türkiye",
}


def main() -> None:
    verify = "--verify" in sys.argv
    wave = sys.argv[sys.argv.index("--wave") + 1] if "--wave" in sys.argv else None

    scan = json.load(open(PATH_SCAN, encoding="utf-8"))
    country_by = {c["name"]: c["country"] for c in scan["candidates"]}

    cache = {}
    if os.path.exists(PATH_CACHE):
        cache = json.load(open(PATH_CACHE, encoding="utf-8"))
    full = [] if not os.path.exists(PATH_OUT) else json.load(open(PATH_OUT, encoding="utf-8"))
    # Garante uma entrada por candidato (inicializa os que ainda não existem)
    known = {r["name"]: r for r in full}
    for c in scan["candidates"]:
        if c["name"] not in known:
            rr = {"name": c["name"], "query": c["name"], "status": "pending",
                  "id": None, "sofascore_name": None, "wave": c["wave"],
                  "country": c.get("country")}
            known[c["name"]] = rr
            full.append(rr)
    if wave:
        out = [r for r in full if str(r.get("wave")) == str(wave)]
        rest = [r for r in full if str(r.get("wave")) != str(wave)]
    else:
        out, rest = full, []

    try:
        for r in out:
            name = r["name"]
            expected_country = country_by.get(name)
            if verify and name.lower() in FORCE_REVIEW:
                r["status"] = "review"
                r["note"] = FORCE_REVIEW[name.lower()]
            elif verify and name.lower() in CONFIRMED:
                # ID já confirmado manualmente — usa o valor travado (sem re-search)
                r["id"] = CONFIRMED[name.lower()]
                r.pop("status", None)
            elif verify and name.lower() in CURATED_QUERY:
                q = CURATED_QUERY[name.lower()]
                r["query"] = q
                r.pop("status", None)
                hits = _search(q, cache)
                hits = [h for h in hits
                        if not any(t in _norm(h.get("name") or "")
                                   for t in _CUP_TERMS + _YOUTH_TERMS)]
                chosen = None
                for h in hits[:10]:
                    d = _details(h["id"], cache)
                    if d.get("sport") == "Football":
                        chosen = h
                        break
                    time.sleep(1.0)
                if chosen:
                    r["id"], r["sofascore_name"] = chosen["id"], chosen["name"]
                time.sleep(1.2)
            if verify and r.get("id"):
                d = _details(r["id"], cache)
                r["sport"] = d["sport"]
                r["country"] = d["country"]
                r["sofascore_name"] = d["name"] or r.get("sofascore_name")
                ok_sport = (d["sport"] == "Football")
                exp_cnt = COUNTRY_ALIAS.get(expected_country, expected_country) if expected_country else ""
                ok_country = (_norm(exp_cnt) in (_norm(d["country"]) or "")) if exp_cnt else True
                r["status"] = "resolved" if (ok_sport and ok_country) else "review"
                r["verification"] = {"sport": d["sport"], "country": d["country"]}
                time.sleep(1.2)
            if verify and name.lower() in FORCE_REVIEW:
                r["status"] = "review"
                r["note"] = FORCE_REVIEW[name.lower()]
    finally:
        json.dump(cache, open(PATH_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(rest + out, open(PATH_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    for r in out:
        print(f"[{r.get('status','?'):>8}] {r['name']:<45} -> id {r.get('id')} "
              f"{r.get('sofascore_name','')} | {r.get('sport')} {r.get('country') or ''}")
    n_res = sum(1 for r in out if r["status"] == "resolved")
    n_rev = sum(1 for r in out if r["status"] == "review")
    print(f"\n{len(out)} | {n_res} verificadas ok | {n_rev} revisar")
    print(f"Salvo em: {PATH_OUT}")


if __name__ == "__main__":
    main()