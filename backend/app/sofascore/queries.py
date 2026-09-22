"""Read-only DB queries: sync status, match dataset, league list."""
from __future__ import annotations

from .. import db
from ..columns import LEAGUES, MATCHES, prefixed


def status() -> dict:
    """Read-only compatibility status backed by the durable jobs table.

    No thread/daemon state is used. Contract keys kept for old callers.
    """
    from .. import jobs

    recent = jobs.list_jobs(limit=10, job_type="sync_all")
    recent.extend(jobs.list_jobs(limit=10, job_type="sync_league"))
    recent.sort(key=lambda j: j.get("id", 0), reverse=True)
    active = [j for j in recent if j.get("status") in ("pending", "running")]
    completed = [j for j in recent if j.get("status") == "completed"]
    total = max(len(recent), 1)
    last = recent[0] if recent else None
    return {
        "running": bool(active),
        "done": len(completed),
        "total": total,
        "current": active[0].get("parameters", "") if active else "",
        "ok": len(completed),
        "fail": sum(1 for j in recent if j.get("status") == "failed"),
        "errors": [{"job_id": j["id"], "error": j.get("error_message")}
                   for j in recent if j.get("status") == "failed"],
        "finished_at": last.get("finished_at") if last else None,
        "error": last.get("error_message") if last and last.get("status") == "failed" else None,
    }
def dataset(league_id: int | None = None, limit: int = 2000,
            next_round: bool = False) -> list[dict]:
    """Lista os jogos (com stats) do banco, opcionalmente filtrado por liga.

    `next_round=True` → apenas a próxima rodada agendada de cada liga
    (menor round com jogos futuros; por isso a seleção é por liga).
    """
    q = (f"SELECT {prefixed(MATCHES, 'm')}, "
         "th.name AS home, ta.name AS away, l.name AS league_name "
         "FROM matches m "
         "JOIN teams th ON th.id=m.home_team_id "
         "JOIN teams ta ON ta.id=m.away_team_id "
         "JOIN leagues l ON l.id=m.league_id ")
    conds: list[str] = []
    params: list = []
    if league_id:
        conds.append("m.league_id=?")
        params.append(league_id)
    if next_round:
        conds.append("m.kickoff_datetime >= datetime('now')")
        conds.append(
            "m.round = (SELECT MIN(m2.round) FROM matches m2 "
            "WHERE m2.league_id=m.league_id AND m2.status='scheduled' "
            "AND m2.kickoff_datetime >= datetime('now') "
            "AND m2.round IS NOT NULL)")
    if conds:
        q += "WHERE " + " AND ".join(conds) + " "
    q += "ORDER BY m.kickoff_datetime {}, m.id LIMIT ?".format(
        "ASC" if next_round else "DESC")
    params.append(limit)
    return [dict(r) for r in db.run_query(q, tuple(params))]
def leagues() -> list[dict]:
    """Ligas no banco com contagem de jogos."""
    return [dict(r) for r in db.run_query(
        f"SELECT {LEAGUES}, "
        " (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='played') AS played, "
        " (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='scheduled') AS scheduled "
        "FROM leagues l ORDER BY l.name")]
