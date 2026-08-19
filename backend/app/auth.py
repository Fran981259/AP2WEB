"""Autenticação JWT — cadastro e login de usuários."""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db

SECRET_KEY = os.environ.get(
    "AP2WEB_SECRET",
    "dev-secret-change-me-please-use-env-var-0123456789abcdef"[:64])
ALGO = "HS256"
TOKEN_TTL = 60 * 60 * 24  # 24h

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return hmac.compare_digest(check, digest)


def create_user(username: str, password: str) -> int:
    if not username.strip() or len(password) < 6:
        raise HTTPException(status_code=400, detail="Usuário obrigatório e senha com mínimo de 6 caracteres")
    try:
        return db.run_exec(
            "INSERT INTO users(username,password_hash) VALUES(?,?)",
            (username.strip(), hash_password(password)))
    except Exception:
        raise HTTPException(status_code=409, detail="Usuário já existe")


def authenticate(username: str, password: str) -> dict:
    rows = db.run_query("SELECT * FROM users WHERE username=?", (username.strip(),))
    if not rows or not verify_password(password, rows[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = jwt.encode({"sub": rows[0]["username"], "exp": time.time() + TOKEN_TTL},
                       SECRET_KEY, algorithm=ALGO)
    return {"token": token, "username": rows[0]["username"]}


def current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    return payload["sub"]