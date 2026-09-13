"""Context Features — modificadores contextuais do λ (FASE 14, FEATURE-001).

Princípio de design (BASE.md §36 Veracidade):
  - Toda feature é calculada "as-of" (nunca usa dados futuros)
  - Todo modificador é multiplicativo e limitado (bounds explícitos)
  - Nenhum modificador substitui o cálculo matemático do Poisson (regra §7)

Features implementadas:
  1. rest_days_factor — fadiga: dias desde a última partida vs mediana da liga
  2. form_slope_factor — momentum: saldo de gols médio recente
  3. team_ha_factor — home advantage próprio do time (PPG casa / PPG fora)

Fórmulas (padrão na literatura de modelagem de futebol):
  resto:  factor = 1 + k_r * (rest - mediana_liga) / 7
  forma:  factor = 1 + k_f * gd_avg_recente
  HA:     factor = (ppg_home + 0.5) / (ppg_away + 0.5)  [suavizado]

Todos estão limitados a [FLOOR, CAP] para nunca explodir probabilidades.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from . import db

# Limites de segurança para qualquer fator multiplicativo
FLOOR = 0.90
CAP = 1.12

# Se nenhum dado disponível, retorna neutro (1.0)
NEUTRAL = 1.0


def _clip(factor: float, floor: float = FLOOR, cap: float = CAP) -> float:
    return max(floor, min(cap, factor))


def _parse_date(ts: Optional[str]) -> Optional[datetime]:
    """Converte kickoff_datetime do SQLite em datetime naive (UTC)."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _team_last_rest_days(league_id: int, team_id: int,
                         match_kickoff: float) -> Optional[float]:
    """Dias de descanso do time antes do kickoff (fração de dia)."""
    ts = datetime.utcfromtimestamp(match_kickoff) if match_kickoff else None
    rows = db.run_query(
        "SELECT kickoff_datetime FROM matches "
        "WHERE league_id=? AND (home_team_id=? OR away_team_id=?) "
        "AND status='played' AND kickoff_datetime IS NOT NULL "
        "AND datetime(kickoff_datetime) < datetime(?) "
        "ORDER BY kickoff_datetime DESC LIMIT 1",
        (league_id, team_id, team_id, ts.isoformat()))
    if not rows:
        return None
    last = _parse_date(rows[0]["kickoff_datetime"])
    if not last or not ts:
        return None
    delta = (ts - last).total_seconds() / 86400.0
    return max(0.0, delta)


def _league_median_rest(league_id: int, as_of: Optional[str] = None) -> Optional[float]:
    """Mediana de dias entre jogos na liga (sample recente, respeitando as-of)."""
    query = (
        "SELECT kickoff_datetime FROM matches "
        "WHERE league_id=? AND status='played' "
        "  AND kickoff_datetime IS NOT NULL "
    )
    params: list = [league_id]
    if as_of:
        query += "AND datetime(kickoff_datetime) < datetime(?) "
        params.append(as_of)
    query += "ORDER BY kickoff_datetime DESC LIMIT 120"
    rows = db.run_query(query, tuple(params))
    dates = [_parse_date(r["kickoff_datetime"]) for r in rows]
    dates = [d for d in dates if d]
    if len(dates) < 10:
        return 7.0
    dates.sort()
    gaps = []
    for a, b in zip(dates, dates[1:]):
        gap = (b - a).total_seconds() / 86400.0
        if 0 < gap < 30:
            gaps.append(gap)
    if not gaps:
        return 7.0
    gaps.sort()
    n = len(gaps)
    mid = n // 2
    return gaps[mid] if n % 2 else (gaps[mid - 1] + gaps[mid]) / 2


def rest_days_factor(league_id: int, team_id: int,
                     match_kickoff_ts: Optional[float],
                     strength: float = 0.15,
                     as_of: Optional[str] = None) -> float:
    """Fator de fadiga. rest < mediana (pouco descanso) → λ menor.

    Nenhum dado → neutro 1.0. Bounds [0.90, 1.12]. `as_of` evita que a mediana
    da liga vaze jogos futuros em avaliações walk-forward.
    """
    if strength <= 0 or not match_kickoff_ts:
        return NEUTRAL
    rest = _team_last_rest_days(league_id, team_id, match_kickoff_ts)
    if rest is None:
        return NEUTRAL
    median = _league_median_rest(league_id, as_of) or 7.0
    relative = (rest - median) / 7.0   # semanas de diferença da mediana
    factor = 1.0 + strength * relative
    return _clip(factor)


def _team_gd_avg(league_id: int, team_id: int, window: int = 5,
                 as_of: Optional[str] = None) -> Optional[float]:
    """Saldo de gols médio (gols marcados - sofridos) nos últimos `window` jogos.

    as-como cláusula de tempo para evitar data leakage.
    """
    query = (
        "SELECT score_home, score_away, home_team_id, kickoff_datetime FROM matches "
        "WHERE league_id=? AND (home_team_id=? OR away_team_id=?) "
        "AND status='played' AND score_home IS NOT NULL"
    )
    params = [league_id, team_id, team_id]
    if as_of:
        query += " AND datetime(kickoff_datetime) < datetime(?)"
        params.append(as_of)
    query += " ORDER BY kickoff_datetime DESC LIMIT ?"
    params.append(window)
    rows = db.run_query(query, tuple(params))
    if not rows:
        return None
    total = 0.0
    for r in rows:
        home_side = r["home_team_id"] == team_id
        gf = r["score_home"] if home_side else r["score_away"]
        ga = r["score_away"] if home_side else r["score_home"]
        total += (gf - ga)
    return total / len(rows)


def form_slope_factor(league_id: int, team_id: int, window: int = 5,
                      strength: float = 0.08, as_of: Optional[str] = None) -> float:
    """Fator de momentum baseado em saldo médio de gols.

    gd_avg = +0.5 (em forma) → factor ≈ 1 + 0.08*0.5 = 1.04
    gd_avg = -0.5 (mal)      → factor ≈ 0.96
    Bounds [0.90, 1.12].
    """
    if strength <= 0:
        return NEUTRAL
    gd = _team_gd_avg(league_id, team_id, window=window, as_of=as_of)
    if gd is None:
        return NEUTRAL
    return _clip(1.0 + strength * gd)


def _team_ppg(league_id: int, team_id: int, as_home: bool,
              as_of: Optional[str] = None) -> Optional[float]:
    """Pontos por jogo (3/1/0) como mandante ou visitante.

    `as_of` → inclui apenas partidas anteriores (anti data-leakage).
    """
    if as_home:
        where = "home_team_id=?"
    else:
        where = "away_team_id=?"
    query = (
        f"SELECT score_home, score_away FROM matches "
        f"WHERE league_id=? AND {where} AND status='played' "
        "AND score_home IS NOT NULL"
    )
    params = [league_id, team_id]
    if as_of:
        query += " AND datetime(kickoff_datetime) < datetime(?)"
        params.append(as_of)
    rows = db.run_query(query, tuple(params))
    if not rows:
        return None
    pts = 0
    for r in rows:
        if as_home:
            gf, ga = r["score_home"], r["score_away"]
        else:
            gf, ga = r["score_away"], r["score_home"]
        pts += 3 if gf > ga else (1 if gf == ga else 0)
    return pts / len(rows)


def team_ha_factor(league_id: int, team_id: int,
                   as_of: Optional[str] = None) -> float:
    """Fator de mando caseiro do próprio time (as-of).

    PPG casa = 2.0, PPG fora = 1.0 → factor = (2.0+0.5)/(1.0+0.5) = 1.67 → clip 1.12
    PPG casa = 1.0, PPG fora = 1.5 → factor = 1.5/2.0 = 0.75 → clip 0.90
    Bounds [0.90, 1.12]. `as_of` previne data-leakage no walk-forward.
    """
    ppg_home = _team_ppg(league_id, team_id, as_home=True, as_of=as_of)
    ppg_away = _team_ppg(league_id, team_id, as_home=False, as_of=as_of)
    if ppg_home is None or ppg_away is None:
        return NEUTRAL
    return _clip((ppg_home + 0.5) / (ppg_away + 0.5))


def adjust_lambdas(
    lam_home: float,
    lam_away: float,
    league_id: int,
    home_team_id: int,
    away_team_id: int,
    match_kickoff_ts: Optional[float] = None,
    k_rest: float = 0.15,
    k_form: float = 0.08,
    k_team_ha: float = 1.0,
    use_rest: bool = False,
    use_form: bool = False,
    use_team_ha: bool = False,
    as_of: Optional[str] = None,
) -> tuple[float, float]:
    """Aplica modificadores contextuais ao λ. Multiplicativos e limitados.

    usa_* → habilita cada feature individualmente para experimentos controlados.
    """
    fh = 1.0
    fa = 1.0

    if use_rest:
        fh *= rest_days_factor(league_id, home_team_id, match_kickoff_ts, k_rest, as_of=as_of)
        fa *= rest_days_factor(league_id, away_team_id, match_kickoff_ts, k_rest, as_of=as_of)

    if use_form:
        fh *= form_slope_factor(league_id, home_team_id, strength=k_form, as_of=as_of)
        fa *= form_slope_factor(league_id, away_team_id, strength=k_form, as_of=as_of)

    if use_team_ha:
        fh *= (NEUTRAL + k_team_ha * (team_ha_factor(league_id, home_team_id, as_of=as_of) - NEUTRAL))
        fa *= (1.0 / (NEUTRAL + k_team_ha * (team_ha_factor(league_id, away_team_id, as_of=as_of) - NEUTRAL)))

    return round(lam_home * fh, 4), round(lam_away * fa, 4)