"""League scan and multi-match portfolio risk."""
from __future__ import annotations

from typing import Any

from .. import db
from .match import risk_for_match
from .policy import RiskConfig


def risk_league(league_id: int, limit: int = 20,
                config: RiskConfig | None = None,
                as_of: str | None = None) -> list[dict[str, Any]]:
    """Avaliação de risco para os próximos jogos de uma liga."""
    q = ("SELECT m.id FROM matches m "
         "WHERE m.league_id=? AND m.status IN ('fixture','scheduled') AND m.home_team_id IS NOT NULL "
         "ORDER BY m.kickoff_datetime, m.id LIMIT ?")
    rows = db.run_query(q, (league_id, limit))
    return [risk_for_match(r["id"], config, as_of) for r in rows]
def portfolio_risk(matches_risk: list[dict], config: RiskConfig | None = None) -> dict[str, Any]:
    """Análise de risco de portfólio (múltiplos jogos).

    Verifica:
    - Exposição total vs limite diário
    - Correlação implícita (múltiplos sinais no mesmo jogo)
    - Diversificação de odds
    """
    cfg = config or RiskConfig()

    all_signals = []
    for mr in matches_risk:
        all_signals.extend(mr.get("signals", []))

    total_stake = sum(s["stake_suggested"] for s in all_signals)
    total_exposure_pct = (total_stake / cfg.bankroll * 100) if cfg.bankroll > 0 else 0
    daily_ok = total_exposure_pct <= (cfg.max_daily_pct * 100)

    # Contagem por outcome
    outcome_counts = {}
    for s in all_signals:
        k = s["outcome"]
        outcome_counts[k] = outcome_counts.get(k, 0) + 1

    # Diversificação de odds (desvio padrão)
    odds_values = [s["market_odds"] for s in all_signals]
    if len(odds_values) >= 2:
        mean_odds = sum(odds_values) / len(odds_values)
        variance = sum((o - mean_odds) ** 2 for o in odds_values) / len(odds_values)
        odds_std = variance ** 0.5
    else:
        odds_std = 0.0

    # Classificação do portfólio
    risk_level = "BAIXO"
    if total_exposure_pct > cfg.max_daily_pct * 100 * 0.8:
        risk_level = "ALTO"
    elif total_exposure_pct > cfg.max_daily_pct * 100 * 0.5:
        risk_level = "MÉDIO"

    return {
        "total_matches": len(matches_risk),
        "total_signals": len(all_signals),
        "total_stake_suggested": round(total_stake, 2),
        "total_exposure_pct": round(total_exposure_pct, 2),
        "daily_limit_pct": round(cfg.max_daily_pct * 100, 2),
        "daily_ok": daily_ok,
        "risk_level": risk_level,
        "outcome_distribution": outcome_counts,
        "odds_diversity_std": round(odds_std, 3),
        "signals": all_signals,
    }
