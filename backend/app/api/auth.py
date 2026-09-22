"""Authentication routes: register, login, logout, refresh and session identity."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from .. import config, security
from ..auth import (authenticate, create_user, current_user_with_role,
                    logout_session, refresh_session)
from ..ratelimit import rate_limit
from .deps import csrf_protect
from .models import LoginBody, RefreshBody, RegisterBody

settings = config.settings
router = APIRouter()

ACCESS_COOKIE = config.ACCESS_COOKIE
REFRESH_COOKIE = config.REFRESH_COOKIE
CSRF_COOKIE = config.CSRF_COOKIE


def _set_auth_cookies(resp, access: str, refresh: str, csrf: str) -> None:
    secure = settings.cookie_secure
    same = settings.cookie_samesite
    resp.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=secure, samesite=same,
        max_age=settings.access_token_ttl_seconds, path="/")
    resp.set_cookie(
        REFRESH_COOKIE, refresh, httponly=True, secure=secure, samesite=same,
        max_age=settings.refresh_token_ttl_seconds, path="/")
    resp.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite=same,
        max_age=settings.refresh_token_ttl_seconds, path="/")


def _clear_auth_cookies(resp) -> None:
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path="/")
    resp.delete_cookie(CSRF_COOKIE, path="/")


def _public_auth_response(data: dict) -> dict:
    """Return session metadata without exposing bearer or refresh secrets."""
    return {
        "username": data["username"],
        "role": data["role"],
        "session_id": data.get("session_id"),
        "expires_in": data.get("expires_in"),
    }


def _mobile_auth_response(data: dict) -> dict:
    """Return bearer credentials for the native mobile client contract."""
    return {
        "access_token": data["token"],
        "refresh_token": data["refresh_token"],
        "token_type": "bearer",
        "expires_in": data.get("expires_in"),
        "user": {
            "username": data["username"],
            "role": data["role"],
        },
    }


@router.post("/api/register", tags=["auth"])
def register(body: RegisterBody, request: Request, _: None = Depends(rate_limit("register"))):
    create_user(body.username, body.password)
    security.audit_event(request, action="register", success=True, username=body.username,
                         role="user")
    return {"ok": True, "message": "Usuário criado"}


@router.post("/api/login", tags=["auth"])
def login(body: LoginBody, request: Request, _: None = Depends(rate_limit("login"))):
    data = authenticate(body.username, body.password, request)
    resp = JSONResponse(content=_public_auth_response(data))
    _set_auth_cookies(resp, data["token"], data["refresh_token"], data["csrf_token"])
    return resp


@router.post("/api/mobile/auth/login", tags=["mobile-auth"])
def mobile_login(body: LoginBody, request: Request,
                 _: None = Depends(rate_limit("mobile-login"))):
    """Issue bearer credentials for the Expo/React Native client."""
    data = authenticate(body.username, body.password, request)
    return _mobile_auth_response(data)


@router.post("/api/logout", tags=["auth"])
def logout(request: Request, _: None = Depends(csrf_protect),
           __: None = Depends(rate_limit("login"))):
    logout_session(request)
    resp = JSONResponse(content={"ok": True})
    _clear_auth_cookies(resp)
    return resp


@router.post("/api/auth/refresh", tags=["auth"])
def auth_refresh(body: RefreshBody | None = None, request: Request = None,
                 _: None = Depends(csrf_protect),
                 __: None = Depends(rate_limit("refresh"))):
    refresh_raw = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not refresh_raw:
        raise HTTPException(status_code=401, detail="Sessão inválida")
    data = refresh_session(refresh_raw, request)
    resp = JSONResponse(content=_public_auth_response(data))
    _set_auth_cookies(resp, data["token"], data["refresh_token"], data["csrf_token"])
    return resp


@router.post("/api/mobile/auth/refresh", tags=["mobile-auth"])
def mobile_refresh(body: RefreshBody, request: Request,
                   _: None = Depends(rate_limit("mobile-refresh"))):
    """Rotate a mobile refresh token without requiring cookies or CSRF."""
    if not body.refresh_token:
        raise HTTPException(status_code=401, detail="Sessão inválida")
    data = refresh_session(body.refresh_token, request)
    return _mobile_auth_response(data)


@router.post("/api/mobile/auth/logout", tags=["mobile-auth"])
def mobile_logout(request: Request, _: None = Depends(csrf_protect),
                  __: None = Depends(rate_limit("mobile-logout"))):
    """Revoke the bearer session family for a native client."""
    return {"ok": True, **logout_session(request)}


@router.get("/api/me", tags=["auth"])
def me(user: dict = Depends(current_user_with_role)):
    return {"username": user["username"], "role": user["role"],
            "session_id": user.get("session_id"), "user_id": user.get("user_id")}
