"""Ligas suportadas no Sofascore (source única de dados do AP2WEB).

Cada entrada: chave amigável + Sofascore unique-tournament ID + nome/país.
O sync puxa automaticamente a temporada mais recente de cada liga.
Lista definida pelo usuário (somente estas ligas).
"""
from __future__ import annotations

import os
from pathlib import Path

import json

LEAGUES_FILE = Path(os.environ.get(
    "AP2WEB_LEAGUES_FILE",
    Path(__file__).resolve().parent / "sofascore_leagues.json"))

# Sofascore unique-tournament IDs (URLs informadas pelo usuário)
# Catálogo histórico. Não é a lista operacional padrão: sincronizar dezenas
# de campeonatos com cobertura desigual transforma o produto em um coletor de
# dados, não em uma plataforma de previsão confiável.
CATALOG_LEAGUES = [
    # ---- Brasil ----
    {"id": 325, "name": "Brasil - Série A", "country": "Brazil"},
    {"id": 390, "name": "Brasil - Série B", "country": "Brazil"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6378 vs baseline 0.6377
    # {"id": 1281, "name": "Brasil - Série C", "country": "Brazil"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6179 vs baseline 0.5869 (Copa, alta variância)
    # {"id": 373, "name": "Brasil - Copa do Brasil", "country": "Brazil"},
    # ---- Continentais ----
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6362 vs baseline 0.625 (amostra 46)
    # {"id": 7, "name": "Europa - Champions League", "country": "Europe"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6956 vs baseline 0.6157 (amostra 30)
    # {"id": 679, "name": "Europa - Europa League", "country": "Europe"},
    {"id": 384, "name": "América do Sul - Libertadores", "country": "South America"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6552 vs baseline 0.6461
    # {"id": 480, "name": "América do Sul - Sudamericana", "country": "South America"},
    {"id": 133, "name": "América do Sul - Copa América", "country": "South America"},
    {"id": 463, "name": "Ásia - AFC Champions League", "country": "Asia"},
    # ---- Inglaterra ----
    {"id": 17, "name": "Inglaterra - Premier League", "country": "England"},
    {"id": 18, "name": "Inglaterra - Championship", "country": "England"},
    {"id": 24, "name": "Inglaterra - League One", "country": "England"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6338 vs baseline 0.6085
    # {"id": 25, "name": "Inglaterra - League Two", "country": "England"},
    {"id": 173, "name": "Inglaterra - National League", "country": "England"},
    # ---- Espanha ----
    {"id": 8, "name": "Espanha - LaLiga", "country": "Spain"},
    {"id": 54, "name": "Espanha - LaLiga 2", "country": "Spain"},
    # ---- Alemanha ----
    {"id": 35, "name": "Alemanha - Bundesliga", "country": "Germany"},
    {"id": 44, "name": "Alemanha - 2. Bundesliga", "country": "Germany"},
    {"id": 491, "name": "Alemanha - 3. Liga", "country": "Germany"},
    # ---- Itália ----
    {"id": 23, "name": "Itália - Serie A", "country": "Italy"},
    {"id": 53, "name": "Itália - Serie B", "country": "Italy"},
    # ---- França ----
    {"id": 34, "name": "França - Ligue 1", "country": "France"},
    {"id": 182, "name": "França - Ligue 2", "country": "France"},
    {"id": 28153, "name": "França - National 2", "country": "France"},
    # ---- Oriente Médio / Ásia ----
    {"id": 955, "name": "Arábia Saudita - Pro League", "country": "Saudi Arabia"},
    # ---- Américas ----
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6527 vs baseline 0.6520
    # {"id": 155, "name": "Argentina - Liga Profesional", "country": "Argentina"},
    {"id": 13475, "name": "Argentina - Copa de la Liga Profesional", "country": "Argentina"},
    {"id": 38, "name": "Bélgica - Pro League", "country": "Belgium"},
    {"id": 9, "name": "Bélgica - Challenger Pro League", "country": "Belgium"},
    {"id": 11653, "name": "Chile - Primera División", "country": "Chile"},
    {"id": 649, "name": "China - Super League", "country": "China"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6579 vs baseline 0.6577
    # {"id": 782, "name": "China - China League", "country": "China"},
    {"id": 11539, "name": "Colômbia - Primera A", "country": "Colombia"},
    {"id": 410, "name": "Coreia do Sul - K League 1", "country": "South Korea"},
    {"id": 170, "name": "Croácia - HNL", "country": "Croatia"},
    {"id": 39, "name": "Dinamarca - Superliga", "country": "Denmark"},
    {"id": 808, "name": "Egito - Premier League", "country": "Egypt"},
    {"id": 240, "name": "Equador - LigaPro Serie A", "country": "Ecuador"},
    {"id": 36, "name": "Escócia - Premiership", "country": "Scotland"},
    {"id": 178, "name": "Estônia - Premium Liiga", "country": "Estonia"},
    {"id": 242, "name": "EUA - MLS", "country": "USA"},
    {"id": 41, "name": "Finlândia - Veikkausliiga", "country": "Finland"},
    {"id": 37, "name": "Holanda - Eredivisie", "country": "Netherlands"},
    {"id": 192, "name": "Irlanda - Premier Division", "country": "Ireland"},
    {"id": 196, "name": "Japão - J1 League", "country": "Japan"},
    {"id": 11621, "name": "México - Liga MX Apertura", "country": "Mexico"},
    {"id": 20, "name": "Noruega - Eliteserien", "country": "Norway"},
    {"id": 22, "name": "Noruega - 1. Division", "country": "Norway"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6509 vs baseline 0.6311 (amostra 24)
    # {"id": 11541, "name": "Paraguai - Primera Clausura", "country": "Paraguay"},
    {"id": 11540, "name": "Paraguai - Primera Apertura", "country": "Paraguay"},
    {"id": 406, "name": "Peru - Liga 1", "country": "Peru"},
    {"id": 238, "name": "Portugal - Liga Portugal Betclic", "country": "Portugal"},
    {"id": 239, "name": "Portugal - Liga Portugal 2", "country": "Portugal"},
    {"id": 40, "name": "Suécia - Allsvenskan", "country": "Sweden"},
    {"id": 215, "name": "Suíça - Super League", "country": "Switzerland"},
    {"id": 278, "name": "Uruguai - Primera División", "country": "Uruguay"},
    # ---- FASE 15 · Onda 1 (IDs verificados via resolve_league_ids) ----
    {"id": 45, "name": "Austria - Bundesliga", "country": "Austria"},
    {"id": 247, "name": "Bulgaria - A PFG", "country": "Bulgaria"},
    {"id": 172, "name": "Czech Republic - Synot Liga", "country": "Czech Republic"},
    {"id": 185, "name": "Greece - Super League", "country": "Greece"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6689 vs baseline 0.6348 (amostra 26)
    # {"id": 187, "name": "Hungary - NB I", "country": "Hungary"},
    {"id": 266, "name": "Israel - Ligat ha'Al", "country": "Israel"},
    # FASE 15 gate xG: Malta 0% e NIR 71% (Sofascore não coleta xG dessas ligas)
    # {"id": 629, "name": "Malta - Premier League", "country": "Malta"},
    # {"id": 200, "name": "Northern Ireland - Premiership", "country": "Northern Ireland"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6674 vs baseline 0.6353
    # {"id": 202, "name": "Poland - Exstraklasa", "country": "Poland"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.637 vs baseline 0.5917
    # {"id": 152, "name": "Romania - Liga I", "country": "Romania"},
    {"id": 203, "name": "Russia - RFPL", "country": "Russia"},
    {"id": 212, "name": "Slovenia - PrvaLiga", "country": "Slovenia"},
    {"id": 218, "name": "Ukraine - Premier Liha", "country": "Ukraine"},
    {"id": 254, "name": "Wales - Welsh Premier League", "country": "Wales"},
    # ---- FASE 15 · Onda 2 (IDs verificados via resolve_league_ids) ----
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6408 vs baseline 0.6297
    # {"id": 703, "name": "Argentina - Primera B Nacional", "country": "Argentina"},
    {"id": 16736, "name": "Bolivia - LFPB", "country": "Bolivia"},
    # FASE 15 gate xG: Série D 15% (595 jogos) — Sofascore só dá xG parcial
    # {"id": 10326, "name": "Brazil - Série D", "country": "Brazil"},
    # FASE 15 gate xG: Panamá 0% — fase Clausura sem xG no Sofascore
    # {"id": 11533, "name": "Panama - Liga Panameña de Fútbol", "country": "Panama"},
    {"id": 231, "name": "Venezuela - Primera División", "country": "Venezuela"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6685 vs baseline 0.6598
    # {"id": 136, "name": "Australia - A League", "country": "Australia"},
    {"id": 1900, "name": "India - Indian Super League", "country": "India"},
    {"id": 848, "name": "India - I-League", "country": "India"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6474 vs baseline 0.5912
    # {"id": 402, "name": "Japan - J2 League", "country": "Japan"},
    {"id": 626, "name": "Vietnam - V-League", "country": "Vietnam"},
    {"id": 358, "name": "South Africa - Premier Soccer League", "country": "South Africa"},
    # ---- FASE 15 · Onda 3 (2ª divisões) ----
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.6598 vs baseline 0.5983 (amostra 31)
    # {"id": 135, "name": "Austria - 2. Liga", "country": "Austria"},
    {"id": 131, "name": "Netherlands - Eerste Divisie", "country": "Netherlands"},
    # DISABLED health_check CRÍTICO 2026-09-02: Brier 0.666 vs baseline 0.6574
    # {"id": 229, "name": "Poland - Division 1", "country": "Poland"},
    # FASE 15 gate xG: Romênia Liga II 70% (amostra pequena, revisar depois)
    # {"id": 562, "name": "Romania - Liga II", "country": "Romania"},
    # FASE 15 gate xG: Rússia FNL 0% — Sofascore não coleta xG de ligas russas
    # {"id": 204, "name": "Russia - FNL", "country": "Russia"},
    # FASE 15 gate xG: Escócia Championship 75% (amostra pequena, revisar depois)
    # {"id": 206, "name": "Scotland - Championship", "country": "Scotland"},
    {"id": 46, "name": "Sweden - Superettan", "country": "Sweden"},
    {"id": 98, "name": "Turkey - 1. Lig", "country": "Turkey"},
    # ---- FASE 15 · Onda 4 ----
    {"id": 188, "name": "Iceland - Besta deild karla", "country": "Iceland"},
    {"id": 197, "name": "Latvia - Virslīga", "country": "Latvia"},
]

# Escopo inicial deliberadamente pequeno. São competições com calendário,
# volume e cobertura de estatísticas mais consistentes. O catálogo continua
# acima para uma expansão posterior, que só deve ocorrer após passar pelos
# mesmos gates de qualidade e backtest.
LEAGUES = [
    {"id": 325, "name": "Brasil - Série A", "country": "Brazil"},
    {"id": 17, "name": "Inglaterra - Premier League", "country": "England"},
    {"id": 8, "name": "Espanha - LaLiga", "country": "Spain"},
    {"id": 35, "name": "Alemanha - Bundesliga", "country": "Germany"},
    {"id": 23, "name": "Itália - Serie A", "country": "Italy"},
]


def load_leagues() -> list[dict]:
    """Lê a lista operacional do JSON ou o núcleo de cinco ligas."""
    if LEAGUES_FILE.exists():
        try:
            return json.loads(LEAGUES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return LEAGUES


def save_leagues(items: list[dict]) -> None:
    """Persiste a lista editada pelo usuário."""
    LEAGUES_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def by_id(sofascore_id: int) -> dict | None:
    return next((l for l in load_leagues() if l["id"] == sofascore_id), None)
