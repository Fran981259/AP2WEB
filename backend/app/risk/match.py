"""Per-match risk assessment over market engine output."""
from __future__ import annotations

from typing import Any

from ..market import LABELS_PT, OUTCOMES, market_for_match
from .policy import RiskConfig, _risk_score, fractional_label, kelly_fraction, kelly_full


def risk_for_match(match_id: int, config: RiskConfig | None = None,
                   as_of: str | None = None,
                   market_odds: dict[str, float] | None = None) -> dict[str, Any]:
    """Avaliação de risco completa para um jogo.

    Retorna:
      - market: dados do market engine (fair_odds, market_odds, ev, kelly)
      - risk: limites calculados, stake sugerida, score de confiança
      - signals: lista de value bets com rating
    """
    cfg = config or RiskConfig()
    mkt = market_for_match(match_id, as_of, market=market_odds)
    probs = mkt["probs"]
    fair = mkt["fair_odds"]
    mkt_odds = mkt["market_odds"] or {}
    ev = mkt["ev"] or {}
    market_available = bool(mkt["market_available"])

    # Kelly fracionado para cada outcome
    kelly_adj = {}
    for k in OUTCOMES:
        if not market_available:
            continue
        kelly_adj[k] = kelly_fraction(probs[k], mkt_odds[k], cfg.kelly_fraction)

    # Limites de exposição
    max_stake = cfg.max_stake()
    max_exposure = cfg.max_exposure_per_match()
    max_daily = cfg.max_daily_exposure()

    # Sinais de value bet
    signals = []
    for k in OUTCOMES:
        # Fair/model odds are not executable market prices. Without a validated
        # external quote there is no EV, Kelly stake, or value-bet signal.
        if not market_available:
            continue
        edge = ev[k]  # EV = p × odds - 1
        kelly_val = kelly_adj.get(k, 0)
        stake_suggested = round(kelly_val * cfg.bankroll, 2) if kelly_val > 0 else 0.0

        # Guardrails
        if stake_suggested > max_stake:
            stake_suggested = max_stake
        if stake_suggested > max_exposure:
            stake_suggested = max_exposure

        # Score de confiança
        risk_score = _risk_score(probs[k], max(edge, 0), kelly_val, mkt_odds[k])

        # Classificar sinal
        is_value = edge > cfg.min_edge and probs[k] >= cfg.min_prob and mkt_odds[k] <= cfg.max_odds

        if is_value and kelly_val > 0:
            signals.append({
                "outcome": k,
                "label": LABELS_PT[k],
                "prob": round(probs[k], 4),
                "fair_odds": round(fair[k], 3),
                "market_odds": round(mkt_odds[k], 3),
                "edge": round(edge, 4),
                "kelly_full": round(kelly_full(probs[k], mkt_odds[k]), 4),
                "kelly_adjusted": round(kelly_val, 4),
                "stake_suggested": stake_suggested,
                "stake_pct_of_bankroll": round(stake_suggested / cfg.bankroll * 100, 2) if cfg.bankroll > 0 else 0,
                "risk_score": risk_score,
                "is_value": True,
            })

    # Ordenar por score (melhores primeiro)
    signals.sort(key=lambda s: s["risk_score"]["score"], reverse=True)

    return {
        "match_id": match_id,
        "config": {
            "kelly_fraction": cfg.kelly_fraction,
            "kelly_label": fractional_label(cfg.kelly_fraction),
            "bankroll": cfg.bankroll,
            "max_stake": max_stake,
            "max_exposure_per_match": max_exposure,
            "max_daily_exposure": max_daily,
            "min_edge": cfg.min_edge,
            "min_prob": cfg.min_prob,
            "max_odds": cfg.max_odds,
        },
        "market": {
            "market_available": market_available,
            "market_quote": mkt.get("market_quote"),
            "probs": mkt["probs"],
            "fair_odds": mkt["fair_odds"],
            "market_odds": mkt["market_odds"],
            "ev": mkt["ev"],
            "kelly_full": mkt["kelly_full"],
            "kelly_adjusted": kelly_adj,
            "vig": mkt["vig"],
            "overround": mkt["overround"],
            "value_bets": mkt["value_bets"],
        },
        "signals": signals,
        "summary": {
            "total_signals": len(signals),
            "best_signal": signals[0] if signals else None,
            "total_stake_suggested": round(sum(s["stake_suggested"] for s in signals), 2),
            "total_exposure_pct": round(sum(s["stake_suggested"] for s in signals) / cfg.bankroll * 100, 2) if cfg.bankroll > 0 else 0,
            "any_value": len(signals) > 0,
        },
        "model_info": mkt["model_info"],
    }
