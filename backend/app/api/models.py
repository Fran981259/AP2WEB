"""Validated request bodies for the mutating API endpoints."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import config

_ALIASES_OK = ConfigDict(extra="ignore")


class RegisterBody(BaseModel):
    username: str = Field(min_length=config.settings.username_min,
                          max_length=config.settings.username_max,
                          pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=config.settings.password_min,
                          max_length=config.settings.password_max)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=config.settings.username_max)
    password: str = Field(min_length=1, max_length=config.settings.password_max)


class RefreshBody(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200)


class FixtureBody(BaseModel):
    league_id: int = Field(gt=0)
    home_team_id: int = Field(gt=0)
    away_team_id: int = Field(gt=0)


class RoleChangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "operator", "admin"]


class PredictionBody(BaseModel):
    model_config = _ALIASES_OK

    league_id: int = Field(gt=0)
    match_id: int = Field(gt=0)
    home_team_id: int = Field(gt=0)
    away_team_id: int = Field(gt=0)
    home_name: str = Field(min_length=1, max_length=120)
    away_name: str = Field(min_length=1, max_length=120)
    match_date: str | None = Field(default=None, max_length=40)
    pick_type: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    pick_value: str = Field(min_length=1, max_length=50)
    pick_label: str = Field(default="", max_length=120)
    prob: float
    odd: float = Field(gt=0, le=10000)
    payload: dict = Field(default_factory=dict)

    @field_validator("match_date")
    @classmethod
    def _valid_date(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        import datetime as _dt
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                _dt.datetime.strptime(v[:23], fmt if len(v) <= 23 else "%Y-%m-%dT%H:%M:%S")
                return v
            except ValueError:
                continue
        raise ValueError("data inválida")

    @field_validator("prob")
    @classmethod
    def _finite_prob(cls, v):
        import math
        if v is None or not math.isfinite(v) or v < 0 or v > 1:
            raise ValueError("probabilidade deve estar entre 0 e 1")
        return v

    @field_validator("odd")
    @classmethod
    def _finite_odd(cls, v):
        import math
        if v is not None and not math.isfinite(v):
            raise ValueError("odd inválida")
        return v

    @field_validator("pick_value")
    @classmethod
    def _valid_pick_value(cls, value, info):
        pick_type = info.data.get("pick_type")
        valid = (
            (pick_type == "1X2" and value in {"1", "X", "2"})
            or (pick_type == "GOLS" and re.fullmatch(
                r"(?:over|under)_(?:0|[1-9][0-9]*)\.5", value))
            or (pick_type == "BTTS" and value in {"sim", "nao"})
        )
        if not valid:
            raise ValueError("jogada não suportada")
        return value

    @field_validator("pick_type")
    @classmethod
    def _valid_pick_type(cls, value):
        if value not in {"1X2", "GOLS", "BTTS"}:
            raise ValueError("tipo de jogada não suportado")
        return value


class OddsQuoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=120)
    captured_at: str = Field(min_length=20, max_length=40)
    odds: dict[str, float]
    source_event_id: str | None = Field(default=None, max_length=120)
