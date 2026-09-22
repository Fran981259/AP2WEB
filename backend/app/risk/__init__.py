"""FASE 11 — Risk Engine (BASE.md §25).

Camada de gestão de risco entre o Market Engine e a decisão de aposta:
- Kelly fracionado configurável (1/4, 1/2, 3/4, full)
- Limites de exposição (por aposta, por liga, diário)
- Score de confiança composto (prob × edge × kelly)
- Guardrails: stop-loss, max consecutive losses

Tudo determinístico — sem LLM, sem inventar números.

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``risk``.
"""
from __future__ import annotations

from .match import risk_for_match
from .policy import (
    DEFAULT_BANKROLL,
    DEFAULT_KELLY_FRACTION,
    KELLY_PRESETS,
    RiskConfig,
    fractional_label,
    kelly_fraction,
    kelly_full,
)
from .portfolio import portfolio_risk, risk_league

__all__ = [
    "DEFAULT_BANKROLL",
    "DEFAULT_KELLY_FRACTION",
    "KELLY_PRESETS",
    "RiskConfig",
    "fractional_label",
    "kelly_fraction",
    "kelly_full",
    "portfolio_risk",
    "risk_for_match",
    "risk_league",
]
