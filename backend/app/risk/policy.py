"""Risk policy: defaults, RiskConfig, Kelly staking and confidence score."""
from __future__ import annotations

from dataclasses import dataclass


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
