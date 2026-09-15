"""The Odds API adapter for auditable pre-match 1X2 quotes."""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from . import db
from .config import settings
from .odds_store import save_1x2_quote

BASE_URL = "https://api.the-odds-api.com/v4"


def sync_soccer_h2h(sport_key: str, region: str = "eu", timeout: int = 20) -> dict:
    api_key = settings.the_odds_api_key
    if not api_key:
        return {"ok": False, "reason": "THE_ODDS_API_KEY is not configured", "saved": 0}
    response = requests.get(
        f"{BASE_URL}/sports/{sport_key}/odds/",
        params={"apiKey": api_key, "regions": region, "markets": "h2h", "oddsFormat": "decimal"},
        timeout=timeout,
    )
    response.raise_for_status()
    saved = 0
    for event in response.json():
        rows = db.run_query(
            "SELECT m.id FROM matches m JOIN teams h ON h.id=m.home_team_id "
            "JOIN teams a ON a.id=m.away_team_id WHERE m.status='scheduled' "
            "AND datetime(m.kickoff_datetime)=datetime(?) AND lower(h.name)=lower(?) "
            "AND lower(a.name)=lower(?)",
            (event["commence_time"], event["home_team"], event["away_team"]),
        )
        if not rows:
            continue
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                values = {item["name"]: item["price"] for item in market.get("outcomes", [])}
                if event["home_team"] not in values or event["away_team"] not in values or "Draw" not in values:
                    continue
                captured_at = bookmaker.get("last_update") or datetime.now(timezone.utc).isoformat()
                save_1x2_quote(rows[0]["id"], bookmaker["key"], captured_at,
                               {"1": values[event["home_team"]], "X": values["Draw"], "2": values[event["away_team"]]},
                               event.get("id"))
                saved += 1
    return {"ok": True, "saved": saved,
            "requests_remaining": response.headers.get("x-requests-remaining")}
