"""Histórico de previsões — salvar, listar, resolver acertos/erros.

O usuário escolhe um "pick" (tipo + valor) e o app registra. Quando uma partida
relacionada vira 'played' (resultado FT conhecido), a previsão é resolvida como
correct/wrong.
"""
from __future__ import annotations

import json
import re

from . import db


def _result_of_pick(pick_type: str, pick_value: str, ft_home, ft_away) -> bool | None:
    """True=acertou, False=errou, None=indefinido."""
    if ft_home is None or ft_away is None:
        return None
    try:
        fh, fa = int(ft_home), int(ft_away)
    except (TypeError, ValueError):
        return None
    if pick_type == "1X2":
        actual = "1" if fh > fa else ("X" if fh == fa else "2")
        return actual == pick_value
    if pick_type == "GOLS":
        total = fh + fa
        m = re.match(r"^(over|under)_([0-9.]+)", pick_value)
        if not m:
            return None
        side, line = m.group(1), float(m.group(2))
        if side == "over":
            return total > line
        return total < line
    if pick_type == "BTTS":
        both = fh > 0 and fa > 0
        return both if pick_value == "sim" else not both
    if pick_type == "PLACAR":
        return f"{fh}-{fa}" == pick_value
    return None


def _resolve_match_id(match_id: int) -> tuple | None:
    if match_id is None:
        return None
    row = db.run_query(
        "SELECT ft_home, ft_away FROM matches WHERE id=? AND status='played'", (match_id,))
    if not row:
        return None
    return row[0]["ft_home"], row[0]["ft_away"]


def _resolve_fixture(p) -> tuple | None:
    """Tenta achar a partida jogada correspondente ao confronto salvo."""
    row = db.run_query(
        "SELECT ft_home, ft_away FROM matches "
        "WHERE league_id=? AND home_team_id=? AND away_team_id=? AND status='played' "
        "ORDER BY match_date DESC LIMIT 1",
        (p["league_id"], p["home_team_id"], p["away_team_id"]))
    if not row:
        return None
    return row[0]["ft_home"], row[0]["ft_away"]


def save_prediction(user_id, data: dict) -> dict:
    """data: {league_id, match_id?, home_team_id, away_team_id, home_name, away_name,
    match_date?, pick_type, pick_value, pick_label, prob, odd, payload}"""
    pid = db.run_exec(
        "INSERT INTO predictions(user_id,league_id,match_id,home_team_id,away_team_id,"
        "home_name,away_name,match_date,pick_type,pick_value,pick_label,prob,odd,payload) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, data.get("league_id"), data.get("match_id"),
         data.get("home_team_id"), data.get("away_team_id"),
         data.get("home_name"), data.get("away_name"), data.get("match_date"),
         data.get("pick_type"), data.get("pick_value"), data.get("pick_label"),
         data.get("prob"), data.get("odd"),
         json.dumps(data.get("payload", {}), ensure_ascii=False)))
    # resolve na hora se a partida já tiver resultado
    resolve_predictions(user_id)
    row = db.run_query("SELECT * FROM predictions WHERE id=?", (pid,))[0]
    return dict(row)


def list_predictions(user_id, limit: int = 200) -> list[dict]:
    rows = db.run_query(
        "SELECT * FROM predictions WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit))
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"] or "{}")
        out.append(d)
    return out


def delete_prediction(user_id, prediction_id: int) -> bool:
    cur = db.run_exec(
        "DELETE FROM predictions WHERE id=? AND user_id=?", (prediction_id, user_id))
    return cur is not None


def stats(user_id) -> dict:
    total, correct, wrong, pending = 0, 0, 0, 0
    for r in db.run_query(
            "SELECT status, COUNT(*) c FROM predictions WHERE user_id=? GROUP BY status",
            (user_id,)):
        s, c = r["status"], r["c"]
        total += c
        if s == "correct":
            correct = c
        elif s == "wrong":
            wrong = c
        else:
            pending = c
    resolved = correct + wrong
    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "pending": pending,
        "hit_rate": round(correct / resolved * 100, 1) if resolved else 0.0,
    }


def resolve_predictions(user_id) -> int:
    """Resolve previsões pending cuja partida já tem resultado. Retorna nº resolvidas."""
    n = 0
    for p in db.run_query(
            "SELECT * FROM predictions WHERE user_id=? AND status='pending'",
            (user_id,)):
        score = _resolve_match_id(p["match_id"]) or _resolve_fixture(p)
        if score is None:
            continue
        res = _result_of_pick(p["pick_type"], p["pick_value"], score[0], score[1])
        if res is None:
            continue
        db.run_exec(
            "UPDATE predictions SET status=?, resolved_at=datetime('now') WHERE id=?",
            ("correct" if res else "wrong", p["id"]))
        n += 1
    return n