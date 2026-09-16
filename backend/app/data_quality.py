"""Gates transparentes de qualidade para dados de previsão.

Uma previsão não deve parecer confiável só porque o processo está de pé. Este
módulo mede completude, cobertura de xG, volume histórico e frescor do último
sync concluído por liga. Ele não faz chamadas ao provedor externo.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import db
from .config import settings

MIN_PLAYED_MATCHES = 60
MIN_XG_COVERAGE = 0.80
MIN_RESULT_COVERAGE = 0.99


def _age_seconds(value: object | None) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))
    except (TypeError, ValueError):
        return None


def league_quality() -> list[dict]:
    """Retorna um diagnóstico por liga, ordenado por nome.

    ``ready`` significa apenas que a base passou pelos gates mínimos de dados;
    nunca é uma promessa de rentabilidade ou de acerto futuro.
    """
    rows = db.run_query(
        "SELECT l.id, l.name, l.country, l.last_sync, "
        "SUM(CASE WHEN m.status='played' THEN 1 ELSE 0 END) AS played, "
        "SUM(CASE WHEN m.status='scheduled' THEN 1 ELSE 0 END) AS scheduled, "
        "SUM(CASE WHEN m.status='played' AND m.score_home IS NOT NULL "
        " AND m.score_away IS NOT NULL THEN 1 ELSE 0 END) AS results_complete, "
        "SUM(CASE WHEN m.status='played' AND m.xg_home IS NOT NULL "
        " AND m.xg_away IS NOT NULL THEN 1 ELSE 0 END) AS xg_complete "
        "FROM leagues l LEFT JOIN matches m ON m.league_id=l.id "
        "GROUP BY l.id, l.name, l.country, l.last_sync ORDER BY l.name")
    report: list[dict] = []
    for raw in rows:
        row = dict(raw)
        played = int(row.get("played") or 0)
        result_coverage = (int(row.get("results_complete") or 0) / played) if played else 0.0
        xg_coverage = (int(row.get("xg_complete") or 0) / played) if played else 0.0
        age = _age_seconds(row.get("last_sync"))
        if played == 0:
            status, reason = "no_data", "Nenhum jogo concluído foi ingerido."
        elif age is None or age > settings.source_sync_max_age_seconds:
            status, reason = "stale", "O último sync concluído está ausente ou vencido."
        elif result_coverage < MIN_RESULT_COVERAGE:
            status, reason = "incomplete", "Há resultados finais ausentes."
        elif xg_coverage < MIN_XG_COVERAGE:
            status, reason = "incomplete", "A cobertura de xG é insuficiente."
        elif played < MIN_PLAYED_MATCHES:
            status, reason = "insufficient_history", "Ainda não há histórico suficiente para calibração."
        else:
            status, reason = "ready", "Base apta para calibração e backtest."
        report.append({
            "league_id": row["id"], "name": row["name"], "country": row.get("country"),
            "status": status, "reason": reason, "played": played,
            "scheduled": int(row.get("scheduled") or 0),
            "results_coverage": round(result_coverage, 4),
            "xg_coverage": round(xg_coverage, 4), "last_sync": row.get("last_sync"),
            "sync_age_seconds": age, "max_sync_age_seconds": settings.source_sync_max_age_seconds,
            "minimum_played_matches": MIN_PLAYED_MATCHES,
        })
    return report
