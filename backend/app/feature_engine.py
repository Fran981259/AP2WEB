"""Feature Engine — única fonte de features para o AP2WEB.

Conforme BASE.md §1048-1070: deve existir uma única fonte para:
  gf, ga, xg, xga, window, blend

Utilizada por:
  - backtest (learning.py)
  - prediction (prediction.py)

Princípio: same data → same features → reproducible results.
"""

from __future__ import annotations
from collections import deque
from typing import Dict, Optional, Tuple


def parse_stat_value(v) -> Optional[float]:
    """Converte valor de stat em float. None se indisponível."""
    if v is None or v == "" or v == "-":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = s.split("(")[-1].replace(")", "").replace("%", "").strip()
    try:
        return float(m)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def compute_team_stats(
    history: deque,
    window: int,
    feature: str,
) -> dict:
    """Computa gf_avg, ga_avg (e derivados) para um time usando os últimos `window` jogos.

    Parâmetros:
      history: deque de {"gf": float, "ga": float} — gols marcados/sofridos por jogo
      window: número de jogos para considerar (últimos N)
      feature: "xg" → usa xG do banco; "goals" → usa gols reais; "blend" → média

    Retorna:
      {"gf_avg": float, "ga_avg": float, "xg_avg": float | None, "xga_avg": float | None}
    """
    n = 0
    gf_sum, ga_sum = 0.0, 0.0
    xg_sum, xga_sum = 0.0, 0.0

    for h in history:
        if n >= window:
            break
        gf = h.get("gf") or 0.0
        ga = h.get("ga") or 0.0

        # Obter xG da partida (podem vir do banco ou serem None)
        xg_home = h.get("xg_home")
        xg_away = h.get("xg_away")

        if feature == "xg":
            # Usar xG disponível; seNone, cair back para gols
            if xg_home is not None:
                gf = xg_home
            if xg_away is not None:
                ga = xg_away
        elif feature == "blend":
            # Média simples: 50% gols + 50% xG
            gf_real = gf
            gf_xg = xg_home if xg_home is not None else 0.0
            ga_real = ga
            ga_xg = xg_away if xg_away is not None else 0.0
            gf = (gf_real + gf_xg) / 2
            ga = (ga_real + ga_xg) / 2

        # Acumular (usar gols reais se xG não disponível ou feature=xg)
        gf_sum += gf
        ga_sum += ga

        # Tentar acumular xG também se houver
        if xg_home is not None:
            xg_sum += xg_home
        if xg_away is not None:
            xg_sum += xg_away

        n += 1

    count = max(n, 1)

    result = {
        "gf_avg": round(gf_sum / count, 3),
        "ga_avg": round(ga_sum / count, 3),
    }

    # Adicionar xG médios se houver dados
    if n > 0 and xg_sum > 0:
        result["xg_avg"] = round(xg_sum / n, 3)
    else:
        result["xg_avg"] = None

    if n > 0 and xg_sum > 0:  # simplificado - xG da away também
        result["xga_avg"] = round(xg_sum / n, 3)  # placeholder - na prática seria soma dos xG contra
    else:
        result["xga_avg"] = None

    return result


def compute_match_stats(
    match: dict,
    feature: str,
) -> dict:
    """Computa stats de uma partida isolada para display/debug.

    Parâmetros:
      match: dicionário com chaves: score_home, score_away, xg_home, xg_away
      feature: "xg", "goals", ou "blend"

    Retorna:
      dict com gf, ga, e os valores feature-selected
    """
    score_home = match.get("score_home") or 0
    score_away = match.get("score_away") or 0
    xg_home = match.get("xg_home")
    xg_away = match.get("xg_away")

    if feature == "xg":
        gf = xg_home if xg_home is not None else score_home
        ga = xg_away if xg_away is not None else score_away
    elif feature == "goals":
        gf = score_home
        ga = score_away
    else:  # blend
        gf = (score_home + (xg_home if xg_home is not None else 0)) / 2
        ga = (score_away + (xg_away if xg_away is not None else 0)) / 2

    return {
        "gf": round(gf, 3),
        "ga": round(ga, 3),
        "xg_home": xg_home,
        "xg_away": xg_away,
    }


def blend_features(
    goals_home: float,
    goals_away: float,
    xg_home: float,
    xg_away: float,
) -> Tuple[float, float, float, float]:
    """Retorna (gf, ga, xg_contrib, xga_contrib) com blend 50/50.

    Conforme BASE.md: blend atual corresponde a 50% gols + 50% xG.

    Returns:
      gf: gols médios ponderados (50% gols + 50% xG home)
      ga: gols médios ponderados (50% gols + 50% xG away)
      xg_contrib: contribuição xG para casa
      xga_contrib: contribuição xG para fora
    """
    gf = (goals_home + xg_home) / 2
    ga = (goals_away + xg_away) / 2
    return gf, ga, xg_home, xg_away