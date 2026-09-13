"""SQLite integrity/provenance audit. Read-only; no application imports or writes."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def audit(path: Path) -> dict:
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = {"database": str(path), "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
                  "foreign_key_violations": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
                  "counts": {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                             for t in sorted(tables) if t in {"leagues", "teams", "matches", "predictions", "league_models", "jobs"}}}
        if "matches" in tables:
            result["matches"] = dict(conn.execute("SELECT status, COUNT(*) FROM matches GROUP BY status"))
            checks = {
                "played_missing_kickoff": "status='played' AND (kickoff_datetime IS NULL OR datetime(kickoff_datetime) IS NULL)",
                "played_missing_score": "status='played' AND (score_home IS NULL OR score_away IS NULL)",
                "played_future": "status='played' AND datetime(kickoff_datetime)>datetime('now')",
                "scheduled_past": "status='scheduled' AND datetime(kickoff_datetime)<datetime('now')",
                "played_with_both_xg": "status='played' AND xg_home IS NOT NULL AND xg_away IS NOT NULL",
            }
            result["data_checks"] = {k: conn.execute("SELECT COUNT(*) FROM matches WHERE " + v).fetchone()[0] for k, v in checks.items()}
        if "predictions" in tables:
            result["predictions"] = dict(conn.execute("SELECT status, COUNT(*) FROM predictions GROUP BY status"))
            result["prediction_timing"] = dict(zip(
                ["linked", "before_kickoff", "at_kickoff", "after_kickoff"],
                conn.execute("SELECT COUNT(*), SUM(datetime(p.predicted_at)<datetime(m.kickoff_datetime)), "
                             "SUM(datetime(p.predicted_at)=datetime(m.kickoff_datetime)), "
                             "SUM(datetime(p.predicted_at)>datetime(m.kickoff_datetime)) "
                             "FROM predictions p JOIN matches m ON m.id=p.match_id").fetchone()))
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    print(json.dumps(audit(parser.parse_args().database), indent=2))
