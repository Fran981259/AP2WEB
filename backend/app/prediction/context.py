"""Kickoff/context helpers: timestamps, flags and lambda modifiers."""
from __future__ import annotations

from datetime import datetime

from ..context_features import adjust_lambdas
from ..model import (
    build_matrix,
    probabilities,
    proposals as build_proposals,
    top_scores,
)


def _kickoff_ts(kickoff: str | None) -> float | None:
    """Converte kickoff_datetime em timestamp unix (UTC naive)."""
    if not kickoff:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(kickoff.replace("Z", "+0000"), fmt).timestamp()
        except ValueError:
            continue
    try:
        return datetime.strptime(kickoff[:10], "%Y-%m-%d").timestamp()
    except ValueError:
        return None
def _context_flags(model: dict) -> dict:
    # Contextual modifiers are not yet evaluated by the canonical walk-forward
    # backtest. Do not silently activate an unvalidated production path.
    del model
    return {
        "rest": 0,
        "form": 0,
        "team_ha": 0,
    }
def _apply_context(context_flags: dict, lh: float, la: float,
                   league_id: int, home_id: int, away_id: int,
                   kickoff_ts: float | None, as_of: str | None,
                   home_name: str, away_name: str,
                   rho: float) -> dict | None:
    """Aplica modificadores contextuais ao λ e reconstrói probabilidades.

    Retorna None se nenhuma feature estiver habilitada. Sempre veracidade:
    os fatores são limitados e o cálculo Poisson não é substituído (§7).
    """
    if not (context_flags["rest"] or context_flags["form"] or context_flags["team_ha"]):
        return None
    n_h, n_a = adjust_lambdas(
        lh, la, league_id, home_id, away_id,
        match_kickoff_ts=kickoff_ts,
        use_rest=bool(context_flags["rest"]),
        use_form=bool(context_flags["form"]),
        use_team_ha=bool(context_flags["team_ha"]),
        as_of=as_of,
    )
    if (n_h, n_a) == (lh, la):
        return None
    matrix = build_matrix(n_h, n_a, rho)
    probs = probabilities(matrix)
    return {
        "lambdas": {"home": n_h, "away": n_a},
        "probs": probs,
        "top_scores": top_scores(probs["scores"]),
        "proposals": build_proposals(probs, {"home": home_name, "away": away_name},
                                     {"home": n_h, "away": n_a}),
    }
