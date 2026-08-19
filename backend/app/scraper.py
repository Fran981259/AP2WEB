"""Scraper Soccerstats.com → SQLite.

Fontes (mapeadas do HTML real):
  - /latest.asp?league=X      → classificação + próximos jogos
  - /matches.asp              → jogos de hoje com estatísticas por time (home/away)
  - /results.asp?league=X&pmtype=bydate → placares FT/HT de jogos já jogados

Acesso passa no Cloudflare usando HTTP/2 (httpx.Client(http2=True)).
"""
from __future__ import annotations

import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from . import db

BASE_URL = "https://www.soccerstats.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


class ScraperError(Exception):
    pass


def fetch(client: httpx.Client, path: str) -> str:
    url = path if path.startswith("http") else BASE_URL + path
    r = client.get(url)
    if r.status_code != 200:
        raise ScraperError(f"GET {url} -> HTTP {r.status_code}")
    text = r.text
    if "Just a moment" in text[:1000] or "attention required" in text.lower()[:1000]:
        raise ScraperError("Bloqueado pelo Cloudflare")
    return text


def new_client() -> httpx.Client:
    return httpx.Client(http2=True, headers=HEADERS, timeout=30, follow_redirects=True)


# --------------------------------------------------------------------------
# Parser: matches.asp (jogos de hoje + stats por time)
# --------------------------------------------------------------------------

def parse_matches_page(html: str) -> list[dict]:
    """Retorna lista de partidas: league, time_home, time_away, kickoff, stats."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for table in soup.find_all("table"):
        parent = None
        for tr in table.find_all("tr"):
            cls = tr.get("class") or []
            cells = tr.find_all("td")
            if "parent" in cls:
                # cabeçalho da liga: nome + code (do link stats)
                parent = _extract_league(tr)
            elif "child" in cls:
                continue
            elif "team1row" in cls and parent:
                home = _team_cells(cells)
            elif "team2row" in cls and parent and "home" in locals():
                away = _team_cells(cells)
                if home["name"] and away["name"]:
                    out.append({
                        "league_code": parent["code"],
                        "league_name": parent["name"],
                        "home": home,
                        "away": away,
                        "date": datetime.now().date().isoformat(),
                    })
                del home
    return out


def _extract_league(tr) -> dict:
    text = re.sub(r"\s+", " ", tr.get_text(" ", strip=True))
    text = re.sub(r"\s*stats\s*", " ", text)
    # code a partir do link stats: latest.asp?league=spain
    code = None
    link = tr.find("a", href=True)
    if link:
        m = re.search(r"league=([A-Za-z0-9\-_]+)", link["href"])
        if m:
            code = m.group(1)
    m = re.match(r"([A-Za-z ]+?) - (.+?)\s*Matches played", text)
    if not m:
        m = re.match(r"([A-Za-z ]+?) - (.+)", text)
    country = m.group(1).strip() if m else ""
    name = m.group(2).strip() if m else text.strip()
    if not code:
        code = name.lower().replace(" ", "-")
    return {"name": name, "country": country, "code": code}


def _team_cells(cells: list) -> dict:
    def t(i):
        return cells[i].get_text(" ", strip=True) if i < len(cells) else ""

    def f(s: str) -> float:
        s = s.replace("%", "").strip()
        try:
            return float(s)
        except ValueError:
            return 0.0

    name = t(0)
    kickoff = t(1)
    scope = t(2)
    # colunas a partir do GP (índice 3): GP W% FTS CS BTS TG GF GA 1.5+ 2.5+ 3.5+ PPG
    stats = {}
    if len(cells) >= 16:
        stats = {
            "scope": scope,
            "gp": f(t(3)),
            "win_pct": f(t(4)) / 100.0,
            "fts_pct": f(t(5)) / 100.0,
            "cs_pct": f(t(6)) / 100.0,
            "bts_pct": f(t(7)) / 100.0,
            "tg": f(t(8)),
            "gf": f(t(9)),
            "ga": f(t(10)),
            "ov15": f(t(11)) / 100.0,
            "ov25": f(t(12)) / 100.0,
            "ov35": f(t(13)) / 100.0,
            "ppg": f(t(15)),
        }
    return {"name": name, "kickoff": kickoff, "stats": stats}


# --------------------------------------------------------------------------
# Parser: results.asp?pmtype=bydate (placares FT/HT)
# --------------------------------------------------------------------------

def parse_results_page(html: str, league_code: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 6:
            continue
        date_txt = cells[0].get_text(" ", strip=True)
        m = re.match(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+([A-Z][a-z]{2})", date_txt)
        if not m:
            continue
        day, month = int(m.group(1)), _MONTHS.get(m.group(2))
        if not month:
            continue
        year = _guess_year(month)
        home = cells[1].get_text(" ", strip=True)
        away = cells[3].get_text(" ", strip=True)
        score = cells[2].get_text(" ", strip=True)
        fm = re.match(r"(\d+)\s*:\s*(\d+)", score)
        if not fm:
            continue
        ft_home, ft_away = int(fm.group(1)), int(fm.group(2))
        ht_home = ht_away = None
        for c in cells[4:]:
            hm = re.search(r"\((\d+)\s*-\s*(\d+)\)", c.get_text(" ", strip=True))
            if hm:
                ht_home, ht_away = int(hm.group(1)), int(hm.group(2))
                break
        out.append({
            "league_code": league_code,
            "home": {"name": home, "kickoff": None, "stats": {}},
            "away": {"name": away, "kickoff": None, "stats": {}},
            "match_date": f"{year:04d}-{month:02d}-{day:02d}",
            "ht_home": ht_home, "ht_away": ht_away,
            "ft_home": ft_home, "ft_away": ft_away,
            "status": "played",
        })
    return out


def _guess_year(month: int) -> int:
    now = datetime.now()
    # temporada europeia: dez-jan pertencem ao ano seguinte (até ~fev)
    if month >= 1 and month <= 2 and now.month >= 7:
        return now.year + 1
    return now.year


# --------------------------------------------------------------------------
# Persistência
# --------------------------------------------------------------------------

def _get_or_create_league(conn, code: str, name: str = "", country: str = "") -> int:
    if code:
        row = conn.execute("SELECT id FROM leagues WHERE code=?", (code,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO leagues(code,name,country) VALUES(?,?,?)",
                           (code, name or code, country))
        return cur.lastrowid
    # sem code: deriva do nome
    row = conn.execute("SELECT id FROM leagues WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO leagues(code,name,country) VALUES(?,?,?)",
                       (code or name.lower().replace(" ", "-"), name, country))
    return cur.lastrowid


def _get_or_create_team(conn, league_id: int, name: str) -> int:
    row = conn.execute("SELECT id FROM teams WHERE league_id=? AND name=?",
                       (league_id, name)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, name))
    return cur.lastrowid


def save_matches(conn, matches: list[dict]) -> dict:
    """Upsert de partidas. Retorna contagens."""
    saved = 0
    found = len(matches)
    for mt in matches:
        league_id = _get_or_create_league(conn, mt.get("league_code", ""), mt.get("league_name", ""), mt.get("country", ""))
        home_id = _get_or_create_team(conn, league_id, mt["home"]["name"])
        away_id = _get_or_create_team(conn, league_id, mt["away"]["name"])
        match_date = mt.get("match_date") or mt.get("date") or datetime.now().date().isoformat()
        row = conn.execute(
            "SELECT id FROM matches WHERE league_id=? AND home_team_id=? AND away_team_id=? AND match_date=?",
            (league_id, home_id, away_id, match_date)).fetchone()
        if row:
            match_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO matches(league_id,home_team_id,away_team_id,match_date,status,ht_home,ht_away,ft_home,ft_away,source_url) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (league_id, home_id, away_id, match_date,
                 mt.get("status", "scheduled"),
                 mt.get("ht_home"), mt.get("ht_away"),
                 mt.get("ft_home"), mt.get("ft_away"),
                 mt.get("source_url", "")))
            match_id = cur.lastrowid
            saved += 1
        # stats por time (só quando existem) — upsert: limpa antigos da partida
        for side in ("home", "away"):
            stats = mt[side].get("stats") if isinstance(mt[side], dict) else None
            if not stats or not stats.get("gp"):
                continue
            team_id = home_id if side == "home" else away_id
            scope = "home" if side == "home" else "away"
            conn.execute("DELETE FROM team_stats WHERE match_id=? AND team_id=?", (match_id, team_id))
            conn.execute(
                "INSERT INTO team_stats(match_id,team_id,scope,gp,win_pct,fts_pct,cs_pct,bts_pct,tg,gf,ga,ov15,ov25,ov35,ppg) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (match_id, team_id, scope, stats.get("gp"), stats.get("win_pct"),
                 stats.get("fts_pct"), stats.get("cs_pct"), stats.get("bts_pct"),
                 stats.get("tg"), stats.get("gf"), stats.get("ga"),
                 stats.get("ov15"), stats.get("ov25"), stats.get("ov35"), stats.get("ppg")))
    conn.commit()
    return {"found": found, "saved": saved}


# --------------------------------------------------------------------------
# Orquestração
# --------------------------------------------------------------------------

def scrape_today(leagues: list[str] | None = None) -> dict:
    """Raspa matches.asp (todos os jogos de hoje)."""
    client = new_client()
    conn = db.get_conn()
    run_id = db.run_exec(
        "INSERT INTO scrape_runs(source,status) VALUES('matches.asp','running')")
    try:
        html = fetch(client, "/matches.asp")
        matches = parse_matches_page(html)
        if leagues:
            matches = [m for m in matches if m.get("league_code") in leagues or m["league_name"] in leagues]
        counts = save_matches(conn, matches)
        conn.execute("UPDATE scrape_runs SET status='ok',finished_at=datetime('now'),"
                     "matches_found=?,matches_saved=?,leagues_updated=? WHERE id=?",
                     (counts["found"], counts["saved"], len(set(m.get("league_code") for m in matches)), run_id))
        conn.commit()
        return {"run_id": run_id, **counts, "leagues": sorted({m.get("league_code") or m["league_name"] for m in matches})}
    except Exception as e:
        conn.execute("UPDATE scrape_runs SET status='error',finished_at=datetime('now'),error=? WHERE id=?",
                     (str(e)[:500], run_id))
        conn.commit()
        raise
    finally:
        conn.close()
        client.close()


def scrape_league_results(league_code: str) -> dict:
    """Raspa resultados (FT/HT) de uma liga."""
    client = new_client()
    conn = db.get_conn()
    run_id = db.run_exec(
        "INSERT INTO scrape_runs(source,status) VALUES('results.asp','running')")
    try:
        html = fetch(client, f"/results.asp?league={league_code}&pmtype=bydate")
        matches = parse_results_page(html, league_code)
        counts = save_matches(conn, matches)
        conn.execute("UPDATE scrape_runs SET status='ok',finished_at=datetime('now'),"
                     "matches_found=?,matches_saved=?,leagues_updated=1 WHERE id=?",
                     (counts["found"], counts["saved"], run_id))
        conn.commit()
        return {"run_id": run_id, **counts}
    except Exception as e:
        conn.execute("UPDATE scrape_runs SET status='error',finished_at=datetime('now'),error=? WHERE id=?",
                     (str(e)[:500], run_id))
        conn.commit()
        raise
    finally:
        conn.close()
        client.close()