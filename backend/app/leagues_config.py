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
LEAGUES = [
    # ---- Brasil ----
    {"id": 325, "name": "Brasil - Série A", "country": "Brazil"},
    {"id": 390, "name": "Brasil - Série B", "country": "Brazil"},
    {"id": 1281, "name": "Brasil - Série C", "country": "Brazil"},
    {"id": 373, "name": "Brasil - Copa do Brasil", "country": "Brazil"},
    # ---- Continentais ----
    {"id": 7, "name": "Europa - Champions League", "country": "Europe"},
    {"id": 679, "name": "Europa - Europa League", "country": "Europe"},
    {"id": 384, "name": "América do Sul - Libertadores", "country": "South America"},
    {"id": 480, "name": "América do Sul - Sudamericana", "country": "South America"},
    {"id": 133, "name": "América do Sul - Copa América", "country": "South America"},
    {"id": 463, "name": "Ásia - AFC Champions League", "country": "Asia"},
    # ---- Inglaterra ----
    {"id": 17, "name": "Inglaterra - Premier League", "country": "England"},
    {"id": 18, "name": "Inglaterra - Championship", "country": "England"},
    {"id": 24, "name": "Inglaterra - League One", "country": "England"},
    {"id": 25, "name": "Inglaterra - League Two", "country": "England"},
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
    {"id": 155, "name": "Argentina - Liga Profesional", "country": "Argentina"},
    {"id": 13475, "name": "Argentina - Copa de la Liga Profesional", "country": "Argentina"},
    {"id": 38, "name": "Bélgica - Pro League", "country": "Belgium"},
    {"id": 9, "name": "Bélgica - Challenger Pro League", "country": "Belgium"},
    {"id": 11653, "name": "Chile - Primera División", "country": "Chile"},
    {"id": 649, "name": "China - Super League", "country": "China"},
    {"id": 782, "name": "China - China League", "country": "China"},
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
    {"id": 11541, "name": "Paraguai - Primera Clausura", "country": "Paraguay"},
    {"id": 11540, "name": "Paraguai - Primera Apertura", "country": "Paraguay"},
    {"id": 406, "name": "Peru - Liga 1", "country": "Peru"},
    {"id": 238, "name": "Portugal - Liga Portugal Betclic", "country": "Portugal"},
    {"id": 239, "name": "Portugal - Liga Portugal 2", "country": "Portugal"},
    {"id": 40, "name": "Suécia - Allsvenskan", "country": "Sweden"},
    {"id": 215, "name": "Suíça - Super League", "country": "Switzerland"},
    {"id": 278, "name": "Uruguai - Primera División", "country": "Uruguay"},
]


def load_leagues() -> list[dict]:
    """Lê ligas do arquivo JSON se existir, senão usa a lista embutida."""
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