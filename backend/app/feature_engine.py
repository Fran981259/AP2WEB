"""Canonical feature selection and aggregation.

compute_match_stats selects goals/xG/blend ONCE. compute_team_stats aggregates
already selected gf/ga entries, newest first. Missing xG falls back to goals;
zero is an observation, not missing data.
"""
from __future__ import annotations

import math
from functools import lru_cache


def parse_stat_value(value) -> float | None:
    if value is None or value == "" or value == "-":
        return None
    text = str(value).strip()
    for candidate in (text.split("(")[-1].replace(")", "").replace("%", "").strip(), text):
        try:
            number = float(candidate)
            return number if math.isfinite(number) else None
        except ValueError:
            continue
    return None


def compute_match_stats(match: dict, feature: str) -> dict:
    """Select match features from home/away-oriented raw score and xG fields."""
    if feature not in {"goals", "xg", "blend"}:
        raise ValueError(f"Unknown feature: {feature}")
    sh = float(match.get("score_home") or 0)
    sa = float(match.get("score_away") or 0)
    xh = parse_stat_value(match.get("xg_home"))
    xa = parse_stat_value(match.get("xg_away"))
    gf, ga = sh, sa
    if feature == "xg":
        gf, ga = xh if xh is not None else sh, xa if xa is not None else sa
    elif feature == "blend":
        gf = (sh + xh) / 2 if xh is not None else sh
        ga = (sa + xa) / 2 if xa is not None else sa
    return {"gf": round(gf, 3), "ga": round(ga, 3), "xg_home": xh, "xg_away": xa}


def team_match_stats(match: dict, team_id: int, feature: str) -> dict:
    """Project a raw match to the requested team's perspective, including xG."""
    stats = compute_match_stats(match, feature)
    if team_id == match["home_team_id"]:
        return stats
    if team_id != match["away_team_id"]:
        raise ValueError("Team does not participate in match")
    return {"gf": stats["ga"], "ga": stats["gf"],
            "xg_home": stats["xg_away"], "xg_away": stats["xg_home"]}


@lru_cache(maxsize=2048)
def _cached_team_stats(history_tuple: tuple, window: int, feature: str) -> dict:
    rows = history_tuple[:window]
    n = len(rows)
    xg = [r[2] for r in rows if r[2] is not None]
    xga = [r[3] for r in rows if r[3] is not None]
    return {
        "gf_avg": round(sum(r[0] for r in rows) / n, 3) if n else 0.0,
        "ga_avg": round(sum(r[1] for r in rows) / n, 3) if n else 0.0,
        "xg_avg": round(sum(xg) / len(xg), 3) if xg else None,
        "xga_avg": round(sum(xga) / len(xga), 3) if xga else None,
    }


def compute_team_stats(history, window: int, feature: str) -> dict:
    """Aggregate selected gf/ga; callers must select features before aggregation."""
    if window < 1 or feature not in {"goals", "xg", "blend"}:
        raise ValueError("Invalid window or feature")
    rows = tuple((h["gf"], h["ga"], h.get("xg_home"), h.get("xg_away")) for h in history)
    # Do not expose the mutable object stored in the cache to callers.
    return dict(_cached_team_stats(rows, window, feature))


def window_stats(matches: list[dict], team_id: int, window: int, feature: str) -> dict:
    rows = [team_match_stats(m, team_id, feature) for m in matches
            if team_id in (m["home_team_id"], m["away_team_id"])][:window]
    if not rows:
        return {"gf_avg": 1.2, "ga_avg": 1.2}
    stats = compute_team_stats(rows, window, feature)
    return {"gf_avg": stats["gf_avg"], "ga_avg": stats["ga_avg"]}
