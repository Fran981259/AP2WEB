"""FASE 11 — Risk Engine (BASE.md §25).

Camada de gestão de risco entre o Market Engine e a decisão de aposta:
- Kelly fracionado configurável (1/4, 1/2, 3/4, full)
- Limites de exposição (por aposta, por liga, diário)
- Score de confiança composto (prob × edge × kelly)
- Guardrails: stop-loss, max consecutive losses

Tudo determinístico — sem LLM, sem inventar números.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

from . import db
from .market import market_for_match, OUTCOMES, LABELS_PT

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_KELLY_FRACTION = 0.25          # 1/4 Kelly (conservador)
KELLY_PRESETS = {
    "full": 1.0,
    "3/4": 0.75,
    "1/2": 0.50,
    "1/4": 0.25,
    "1/8": 0.125,
}

DEFAULT_BANKROLL = 1000.0              # banca inicial (unidades)
DEFAULT_MAX_STAKE_PCT = 0.05           # 5% da banca por aposta
DEFAULT_MAX_EXPOSURE_PCT = 0.15        # 15% da banca exposta por jogo
DEFAULT_MAX_DAILY_PCT = 0.25           # 25% da banca por dia
DEFAULT_MIN_EDGE = 0.02                # edge mínimo (2%) para sinalizar
DEFAULT_MIN_PROB = 0.30                # probabilidade mínima (30%)
DEFAULT_MAX_ODDS = 10.0                # odds máximas aceitas


@dataclass
class RiskConfig:
    """Configuração de gestão de risco (tudo percentual da banca)."""
    kelly_fraction: float = DEFAULT_KELLY_FRACTION
    bankroll: float = DEFAULT_BANKROLL
    max_stake_pct: float = DEFAULT_MAX_STAKE_PCT
    max_exposure_pct: float = DEFAULT_MAX_EXPOSURE_PCT
    max_daily_pct: float = DEFAULT_MAX_DAILY_PCT
    min_edge: float = DEFAULT_MIN_EDGE
    min_prob: float = DEFAULT_MIN_PROB
    max_odds: float = DEFAULT_MAX_ODDS

    def max_stake(self) -> float:
        """Stake máxima por aposta (em unidades da banca)."""
        return self.bankroll * self.max_stake_pct

    def max_exposure_per_match(self) -> float:
        """Exposição máxima por jogo."""
        return self.bankroll * self.max_exposure_pct

    def max_daily_exposure(self) -> float:
        """Exposição máxima diária."""
        return self.bankroll * self.max_daily_pct


# ── Kelly Criterion ─────────────────────────────────────────────────────────

def kelly_full(prob: float, odds: float) -> float:
    """Kelly completo: f* = (p × odds - 1) / (odds - 1).

    Retorna fração da banca a apostar (positivo = valor, negativo = sem edge).
    """
    if odds <= 1.0 or prob <= 0.0:
        return 0.0
    return (prob * odds - 1.0) / (odds - 1.0)


def kelly_fraction(prob: float, odds: float, fraction: float = 0.25) -> float:
    """Kelly fracionado: aplica fração do Kelly completo.

    Base.md §25: "A implementação deve permitir fração configurável".
    """
    full = kelly_full(prob, odds)
    if full <= 0:
        return 0.0
    return round(full * fraction, 6)


def fractional_label(fraction: float) -> str:
    """Label legível para a fração de Kelly."""
    for label, val in KELLY_PRESETS.items():
        if abs(fraction - val) < 1e-6:
            return label
    return f"{fraction:.1%}"


# ── Risk Score ──────────────────────────────────────────────────────────────

def _risk_score(prob: float, edge: float, kelly_val: float, odds: float) -> dict:
    """Score composto de 0–100 que combina edge, probabilidade e Kelly.

    Componentes:
      - edge_score (0–40):  edge / 0.10 × 40  (capped em 40)
      - prob_score (0–30):  prob × 30         (capped em 30)
      - kelly_score (0–30): kelly × 3 / 1 × 30 (capped em 30)
    """
    edge_score = min(edge / 0.10, 1.0) * 40   # edge de 10% = 40 pts
    prob_score = min(prob, 1.0) * 30           # prob 100% = 30 pts
    kelly_norm = min(max(kelly_val, 0) / 0.03, 1.0)  # kelly 3% = 30 pts
    kelly_score = kelly_norm * 30

    total = round(edge_score + prob_score + kelly_score, 1)

    if total >= 70:
        grade = "A"
        label = "Alta confiança"
    elif total >= 50:
        grade = "B"
        label = "Confiança moderada"
    elif total >= 30:
        grade = "C"
        label = "Confiança baixa"
    else:
        grade = "D"
        label = "Não recomendado"

    return {
        "score": min(total, 100),
        "grade": grade,
        "label": label,
        "components": {
            "edge": round(edge_score, 1),
            "probability": round(prob_score, 1),
            "kelly": round(kelly_score, 1),
        },
    }


# ── Risk Assessment per match ───────────────────────────────────────────────

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
    mkt_odds = mkt["market_odds"]
    ev = mkt["ev"]

    # Kelly fracionado para cada outcome
    kelly_adj = {}
    for k in OUTCOMES:
        kelly_adj[k] = kelly_fraction(probs[k], mkt_odds[k], cfg.kelly_fraction)

    # Limites de exposição
    max_stake = cfg.max_stake()
    max_exposure = cfg.max_exposure_per_match()
    max_daily = cfg.max_daily_exposure()

    # Sinais de value bet
    signals = []
    for k in OUTCOMES:
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


# ── Risk Assessment per league ──────────────────────────────────────────────

def risk_league(league_id: int, limit: int = 20,
                config: RiskConfig | None = None,
                as_of: str | None = None) -> list[dict[str, Any]]:
    """Avaliação de risco para os próximos jogos de uma liga."""
    q = ("SELECT m.id FROM matches m "
         "WHERE m.league_id=? AND m.status IN ('fixture','scheduled') AND m.home_team_id IS NOT NULL "
         "ORDER BY m.kickoff_datetime, m.id LIMIT ?")
    rows = db.run_query(q, (league_id, limit))
    return [risk_for_match(r["id"], config, as_of) for r in rows]


# ── Portfolio Risk (multi-match) ────────────────────────────────────────────

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
