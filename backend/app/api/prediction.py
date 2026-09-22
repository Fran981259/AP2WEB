"""Prediction routes: engine queries, comparison and user prediction history."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path
from fastapi.routing import APIRouter

from ..auth import current_user
from ..history import delete_prediction, list_predictions, save_prediction, stats
from ..prediction import predict_fixture, predict_league_upcoming, predict_match
from ..ratelimit import rate_limit
from .deps import csrf_protect, user_id
from .models import FixtureBody, PredictionBody

router = APIRouter()


@router.get("/api/matches/{match_id}/prediction", tags=["prediction"])
def prediction(match_id: int = Path(gt=0), user: str = Depends(current_user),
               as_of_timestamp: str | None = None):
    try:
        return predict_match(match_id, as_of_timestamp=as_of_timestamp)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/predict/fixture", tags=["prediction"])
def fixture_prediction(body: FixtureBody, user: str = Depends(current_user),
                       _: None = Depends(csrf_protect),
                       __: None = Depends(rate_limit("fixture")),
                       as_of_timestamp: str | None = None):
    try:
        return predict_fixture(body.league_id, body.home_team_id, body.away_team_id,
                               as_of_timestamp=as_of_timestamp)
    except IndexError:
        raise HTTPException(status_code=404, detail="Confronto não encontrado")


@router.get("/api/leagues/{league_id}/predictions", tags=["prediction"])
def league_predictions(league_id: int = Path(gt=0), user: str = Depends(current_user),
                       as_of_timestamp: str | None = None):
    return predict_league_upcoming(league_id, as_of_timestamp=as_of_timestamp)


@router.get("/api/matches/{match_id}/compare", tags=["prediction"])
def compare_prediction(match_id: int = Path(gt=0), user: str = Depends(current_user)):
    poisson_result = predict_match(match_id, use_bayesian=False)
    bayesian_result = predict_match(match_id, use_bayesian=True)

    poisson = {
        "lambdas": poisson_result.get("lambdas"),
        "probs": poisson_result.get("probs"),
        "top_scores": poisson_result.get("top_scores"),
        "inputs": poisson_result.get("inputs"),
        "model": poisson_result.get("model"),
    }
    bayesian = bayesian_result.get("bayesian")

    return {
        "match": poisson_result.get("match"),
        "poisson": poisson,
        "bayesian": bayesian,
        "comparison": _bayesian_comparison(poisson, bayesian),
    }


def _bayesian_comparison(poisson: dict, bayesian: dict) -> dict:
    if not bayesian:
        return {"status": "bayesian_unavailable"}

    p1x2 = poisson.get("probs", {}).get("1x2", {})
    b1x2 = bayesian.get("probs", {}).get("1x2", {})

    diff = {
        "prob_1_diff": round(b1x2.get("1", 0) - p1x2.get("1", 0), 4),
        "prob_X_diff": round(b1x2.get("X", 0) - p1x2.get("X", 0), 4),
        "prob_2_diff": round(b1x2.get("2", 0) - p1x2.get("2", 0), 4),
    }

    p_lambda_home = poisson.get("lambdas", {}).get("home", 0)
    p_lambda_away = poisson.get("lambdas", {}).get("away", 0)
    b_lambda_home = bayesian.get("lambdas", {}).get("home", 0)
    b_lambda_away = bayesian.get("lambdas", {}).get("away", 0)

    return {
        **diff,
        "lambda_home_poisson": p_lambda_home,
        "lambda_away_poisson": p_lambda_away,
        "lambda_home_bayesian": b_lambda_home,
        "lambda_away_bayesian": b_lambda_away,
        "lambda_home_diff": round(b_lambda_home - p_lambda_home, 3),
        "lambda_away_diff": round(b_lambda_away - p_lambda_away, 3),
        "bayesian_weight_home": bayesian.get("home_bayesian_weight", 0),
        "bayesian_weight_away": bayesian.get("away_bayesian_weight", 0),
    }


@router.get("/api/bayesian/league/{league_id}", tags=["prediction"])
def bayesian_league_summary(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    from ..prediction import _get_bayesian_engine
    engine = _get_bayesian_engine(league_id)
    return engine.summary()


@router.post("/api/predictions", tags=["prediction"])
def create_prediction(body: PredictionBody, user: str = Depends(current_user),
                      _: None = Depends(csrf_protect),
                      __: None = Depends(rate_limit("prediction"))):
    try:
        return save_prediction(user_id(user), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/predictions", tags=["prediction"])
def get_predictions(user: str = Depends(current_user)):
    uid = user_id(user)
    return {"stats": stats(uid), "items": list_predictions(uid)}


@router.delete("/api/predictions/{prediction_id}", tags=["prediction"])
def remove_prediction(prediction_id: int = Path(gt=0), user: str = Depends(current_user),
                      _: None = Depends(csrf_protect),
                      __: None = Depends(rate_limit("prediction"))):
    deleted = delete_prediction(user_id(user), prediction_id)
    return {"ok": deleted is not None and deleted is not False}
