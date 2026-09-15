"""FASE 10 — Market Engine (BASE.md §1141).

Gera odds a partir das probabilidades do modelo Poisson:
- fair_odds:      1 / p  (sem margem)
- market_odds:    1 / p com margem de bookmaker (vig) aplicada
- EV:             valor esperado (probabilidade real × odds - 1)

Tudo leak-safe: probabilities são do Poisson walk-forward (FASE 4 as_of
consistente). Odds derivadas são determinísticas da fair_odds.
"""
from __future__ import annotations

from typing import Any

from . import db
from .prediction import predict_match
from .odds_store import latest_1x2_quote

OUTCOMES = ("1", "X", "2")
LABELS_PT = {"1": "Casa", "X": "Empate", "2": "Visita"}

# margem típica de bookmaker (vig) — 4.0% ≈ 1.042
DEFAULT_VIG = 0.040


def _fair_odds(probs: dict[str, float]) -> dict[str, float]:
    return {k: 1.0 / max(probs[k], 1e-6) for k in OUTCOMES}


def _market_odds(fair: dict[str, float], vig: float) -> dict[str, float]:
    """odds de mercado ajustadas pela margem do bookmaker (sobrecobertura)."""
    inv_sum = sum(1.0 / v for v in fair.values())
    implied_prob = {k: (1.0 / fair[k]) / (inv_sum * (1 - vig)) for k in OUTCOMES}
    return {k: 1.0 / implied_prob[k] for k in OUTCOMES}


def _ev(probs: dict[str, float], market_odds: dict[str, float]) -> dict[str, float]:
    return {k: round(probs[k] * market_odds[k] - 1.0, 4) for k in OUTCOMES}


def market_for_match(match_id: int, as_of: str | None = None,
                      vig: float = DEFAULT_VIG,
                      market: dict[str, float] | None = None) -> dict[str, Any]:
    """Computa fair / market odds + EV para um jogo.

    Quotes externas são lidas exclusivamente do repositório persistido. O
    parâmetro `market` é ignorado para impedir que entrada não auditada gere EV.
    """
    rows = db.run_query("SELECT status FROM matches WHERE id=?", (match_id,))
    if not rows:
        raise IndexError("Partida não encontrada")
    if rows[0]["status"] != "scheduled":
        raise ValueError("Market analysis is available only for scheduled matches")
    pred = predict_match(match_id, as_of)
    probs = pred["probs"]["1x2"]

    fair = _fair_odds(probs)
    del market
    quote = latest_1x2_quote(match_id, as_of)
    market_available = quote is not None
    mkt = quote["odds"] if quote else None
    ev = _ev(probs, mkt) if mkt else None

    # overround (margem implícita do bookmaker)
    overround = sum(1.0 / mkt[k] for k in OUTCOMES) if mkt else None

    # kelly fracionado (FASE 11 baseline; aqui exposto como EV Kelly)
    kelly = ({k: round((mkt[k] * probs[k] - 1.0) / (mkt[k] - 1.0), 4)
              for k in OUTCOMES if mkt[k] > 1.0} if mkt else {})

    return {
        "match_id": match_id,
        "probs": {k: round(probs[k], 6) for k in OUTCOMES},
        "fair_odds": {k: round(fair[k], 3) for k in OUTCOMES},
        "market_available": market_available,
        "market_quote": ({"provider": quote["provider"], "captured_at": quote["captured_at"]}
                         if quote else None),
        "market_odds": {k: round(mkt[k], 3) for k in OUTCOMES} if mkt else None,
        "ev": ev,
        "kelly_full": kelly,  # FASE 11: fracionar depois
        "vig": vig if mkt else None,
        "overround": round(overround, 4) if overround is not None else None,
        "value_bets": [k for k in OUTCOMES if ev and ev[k] > 0],
        "model_info": pred["model"],
    }


def market_league(league_id: int, limit: int = 20,
                  as_of: str | None = None,
                  vig: float = DEFAULT_VIG) -> list[dict[str, Any]]:
    """Fair + market odds + EV para os próximos jogos de uma liga."""
    q = ("SELECT m.id FROM matches m "
          "WHERE m.league_id=? AND m.status='scheduled' AND m.home_team_id IS NOT NULL "
         "ORDER BY m.kickoff_datetime, m.id LIMIT ?")
    rows = db.run_query(q, (league_id, limit))
    return [market_for_match(r["id"], as_of, vig) for r in rows]
