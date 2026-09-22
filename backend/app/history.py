"""Histórico de previsões — salvar, listar, resolver acertos/erros.

O usuário escolhe um "pick" (tipo + valor) e o app registra. Quando uma partida
relacionada vira 'played' (resultado FT conhecido), a previsão é resolvida como
correct/wrong.

FASE 6 — Evaluation Engine:
- model_version: versão do modelo usado
- predicted_at: timestamp da previsão
- brier_score: pontuação Brier (0 = perfeito)
- log_loss: loss logarítmico
- calibration: verificação de calibração
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

from . import db
from .columns import PREDICTIONS


def _brier_score(prob_correct: float) -> float:
    """Pontuação Brier: (1 - p)^2 se acertou, p^2 se errou.
    Varia de 0 (perfeito) a 1 (errado com certeza).
    """
    return (1 - prob_correct) ** 2


def _log_loss(prob_correct: float) -> float:
    """Loss logarítmico: -ln(p) se acertou, -ln(1-p) se errou.
    Problema se p=0 ou p=1 (retorna infinito).
    """
    try:
        if prob_correct <= 0 or prob_correct >= 1:
            return 99.0  # penalidade alta
        return -math.log(prob_correct)
    except (ValueError, OverflowError):
        return 99.0


def _normalize_prob(p: float) -> float:
    """Predictions are stored as decimal probabilities only."""
    return p


def _result_of_pick_v2(pick_type: str, pick_value: str, ft_home, ft_away,
                       prob_home: float) -> dict | None:
    """Retorna dicionário com result, brier, log_loss para a previsão."""
    if ft_home is None or ft_away is None:
        return None
    prob_home = _normalize_prob(prob_home)
    try:
        fh, fa = int(ft_home), int(ft_away)
    except (TypeError, ValueError):
        return None
    if pick_type == "1X2":
        actual = "1" if fh > fa else ("X" if fh == fa else "2")
        hit = actual == pick_value
        brier = _brier_score(prob_home) if hit else _brier_score(1 - prob_home)
        ll = _log_loss(prob_home) if hit else _log_loss(1 - prob_home)
        return {"result": hit, "brier": round(brier, 4), "log_loss": round(ll, 4)}
    if pick_type == "GOLS":
        total = fh + fa
        m = re.fullmatch(r"(over|under)_([0-9]+(?:\.5)?)", pick_value)
        if not m:
            return None
        side, line = m.group(1), float(m.group(2))
        if side == "over":
            hit = total > line
        else:
            hit = total < line
        brier = _brier_score(prob_home) if hit else _brier_score(1 - prob_home)
        ll = _log_loss(prob_home) if hit else _log_loss(1 - prob_home)
        return {"result": hit, "brier": round(brier, 4), "log_loss": round(ll, 4)}
    if pick_type == "BTTS":
        both = fh > 0 and fa > 0
        hit = both if pick_value == "sim" else not both
        brier = _brier_score(prob_home) if hit else _brier_score(1 - prob_home)
        ll = _log_loss(prob_home) if hit else _log_loss(1 - prob_home)
        return {"result": hit, "brier": round(brier, 4), "log_loss": round(ll, 4)}
    if pick_type == "PLACAR":
        return None
    return None


def _resolve_match_id(match_id: int) -> tuple | None:
    if match_id is None:
        return None
    row = db.run_query(
        "SELECT score_home, score_away FROM matches WHERE id=? AND status='played'", (match_id,))
    if not row:
        return None
    return row[0]["score_home"], row[0]["score_away"]


def _resolve_fixture(p) -> tuple | None:
    """Tenta achar a partida jogada correspondente ao confronto salvo."""
    row = db.run_query(
        "SELECT score_home, score_away FROM matches "
        "WHERE league_id=? AND home_team_id=? AND away_team_id=? AND status='played' "
        "ORDER BY kickoff_datetime DESC LIMIT 1",
        (p["league_id"], p["home_team_id"], p["away_team_id"]))
    if not row:
        return None
    return row[0]["score_home"], row[0]["score_away"]


def _validate_pick(pick_type: str, pick_value: str) -> None:
    valid = (
        (pick_type == "1X2" and pick_value in {"1", "X", "2"})
        or (pick_type == "GOLS" and re.fullmatch(
            r"(?:over|under)_(?:0|[1-9][0-9]*)\.5", pick_value))
        or (pick_type == "BTTS" and pick_value in {"sim", "nao"})
    )
    if not valid:
        raise ValueError("jogada não suportada")


def save_prediction(user_id, data: dict) -> dict:
    """data: {league_id, match_id?, home_team_id, away_team_id, home_name, away_name,
    match_date?, pick_type, pick_value, pick_label, prob, odd, payload, model_version, predicted_at}"""
    _validate_pick(data.get("pick_type"), data.get("pick_value"))
    match_id = data.get("match_id")
    match = db.run_query(
        "SELECT m.id, m.league_id, m.home_team_id, m.away_team_id, m.kickoff_datetime, "
        "m.match_date, m.status, th.name home_name, ta.name away_name "
        "FROM matches m JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id WHERE m.id=?", (match_id,))
    if not match:
        raise ValueError("partida não encontrada")
    match = dict(match[0])
    if match["status"] != "scheduled":
        raise ValueError("só é permitido salvar partidas agendadas")
    kickoff = match["kickoff_datetime"]
    if not kickoff:
        raise ValueError("partida sem horário de início")
    try:
        kickoff_at = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        if kickoff_at.tzinfo is None:
            kickoff_at = kickoff_at.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("horário da partida inválido") from exc
    if kickoff_at <= datetime.now(timezone.utc):
        raise ValueError("só é permitido salvar partidas futuras")
    for field in ("league_id", "home_team_id", "away_team_id"):
        if data.get(field) != match[field]:
            raise ValueError("partida não corresponde à liga ou aos times informados")

    # Rebuild provenance from the canonical match instead of accepting client claims.
    provenance = {}
    try:
        from .prediction import predict_match
        provenance = predict_match(match_id).get("provenance") or {}
    except Exception:
        provenance = {}
    provenance_fields = (
        "model_version", "model_method", "feature_version", "data_snapshot_timestamp",
        "as_of_timestamp", "training_window", "training_sample_size", "league_model_version",
        "prediction_created_at", "source_data_freshness", "confidence_level", "fallback_reason",
    )
    canonical = {
        **data,
        "league_id": match["league_id"],
        "match_id": match["id"],
        "home_team_id": match["home_team_id"],
        "away_team_id": match["away_team_id"],
        "home_name": match["home_name"],
        "away_name": match["away_name"],
        "match_date": (kickoff or match["match_date"] or "")[:10] or None,
        **{field: provenance.get(field) for field in provenance_fields},
    }
    model_version = canonical.get("model_version")
    predicted_at = canonical.get("prediction_created_at") or datetime.now(timezone.utc).isoformat()
    pid = db.run_exec(
        "INSERT INTO predictions(user_id,league_id,match_id,home_team_id,away_team_id,"
        "home_name,away_name,match_date,pick_type,pick_value,pick_label,prob,odd,payload,model_version,model_method,feature_version,data_snapshot_timestamp,as_of_timestamp,training_window,training_sample_size,league_model_version,predicted_at,source_data_freshness,confidence_level,fallback_reason) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, canonical.get("league_id"), canonical.get("match_id"),
         canonical.get("home_team_id"), canonical.get("away_team_id"),
          canonical.get("home_name"), canonical.get("away_name"), canonical.get("match_date"),
          canonical.get("pick_type"), canonical.get("pick_value"), canonical.get("pick_label"),
          canonical.get("prob"), canonical.get("odd"),
          json.dumps(canonical.get("payload", {}), ensure_ascii=False),
          model_version, canonical.get("model_method"), canonical.get("feature_version"),
          canonical.get("data_snapshot_timestamp"), canonical.get("as_of_timestamp"),
          canonical.get("training_window"), canonical.get("training_sample_size"),
          canonical.get("league_model_version"), predicted_at,
          canonical.get("source_data_freshness"), canonical.get("confidence_level"), canonical.get("fallback_reason")))
    row = db.run_query(f"SELECT {PREDICTIONS} FROM predictions WHERE id=?", (pid,))[0]
    return dict(row)


def list_predictions(user_id, limit: int = 200) -> list[dict]:
    resolve_predictions(user_id)
    rows = db.run_query(
        f"SELECT {PREDICTIONS} FROM predictions WHERE user_id=? ORDER BY id DESC LIMIT ?",
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
    return cur > 0


def stats(user_id) -> dict:
    resolve_predictions(user_id)
    total, correct, wrong, pending = 0, 0, 0, 0
    for r in db.run_query(
            "SELECT status, COUNT(*) c FROM predictions WHERE user_id=? GROUP BY status",
            (user_id,)):
        s, c = r["status"], r["c"]
        total += c
        if s == "correct":
            correct += c
        elif s == "wrong":
            wrong += c
        else:
            pending += c
    resolved = correct + wrong
    # Calcular média de Brier e Log Loss apenas em previsões resolvidas
    brier_vals = [r["brier_score"] for r in db.run_query(
        "SELECT brier_score FROM predictions WHERE user_id=? AND status IN ('correct','wrong')", (user_id,))]
    ll_vals = [r["log_loss"] for r in db.run_query(
        "SELECT log_loss FROM predictions WHERE user_id=? AND status IN ('correct','wrong')", (user_id,))]
    
    avg_brier = round(sum(brier_vals) / len(brier_vals), 4) if brier_vals else None
    avg_ll = round(sum(ll_vals) / len(ll_vals), 4) if ll_vals else None
    
    hit_rate = round(correct / resolved * 100, 1) if resolved else 0.0
    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "pending": pending,
        "hit_rate": hit_rate,
        "avg_brier": avg_brier,
        "avg_log_loss": avg_ll,
    }


def resolve_predictions(user_id) -> int:
    """Resolve previsões pending cuja partida já tem resultado. Retorna nº resolvidas."""
    n = 0
    for p in db.run_query(
            f"SELECT {PREDICTIONS} FROM predictions WHERE user_id=? AND status='pending'", (user_id,)):
        score = _resolve_match_id(p["match_id"]) if p["match_id"] is not None else _resolve_fixture(p)
        if score is None:
            continue
        # Usar _result_of_pick_v2 para obter brier e log_loss
        prob_home = dict(p).get("prob", 0.5)  # fallback 0.5 se não houver prob
        res_dict = _result_of_pick_v2(p["pick_type"], p["pick_value"], score[0], score[1], prob_home)
        if res_dict is None:
            continue
        db.run_exec(
            "UPDATE predictions SET status=?, resolved_at=datetime('now'), brier_score=?, "
            "log_loss=?, updated_at=datetime('now') WHERE id=?",
            ("correct" if res_dict["result"] else "wrong", res_dict["brier"], res_dict["log_loss"], p["id"]))
        n += 1
    return n


def resolve_predictions_for_match(match_id: int) -> int:
    """Resolve only pending predictions attached to one completed match."""
    score = _resolve_match_id(match_id)
    if score is None:
        return 0
    n = 0
    for p in db.run_query(
            f"SELECT {PREDICTIONS} FROM predictions WHERE match_id=? AND status='pending'", (match_id,)):
        prob_home = dict(p).get("prob", 0.5)
        res_dict = _result_of_pick_v2(
            p["pick_type"], p["pick_value"], score[0], score[1], prob_home)
        if res_dict is None:
            continue
        # The pending condition makes concurrent/repeated syncs idempotent.
        updated = db.run_exec(
            "UPDATE predictions SET status=?, resolved_at=datetime('now'), brier_score=?, log_loss=?, "
            "updated_at=datetime('now') "
            "WHERE id=? AND status='pending'",
            ("correct" if res_dict["result"] else "wrong", res_dict["brier"],
             res_dict["log_loss"], p["id"]))
        n += updated
    return n
