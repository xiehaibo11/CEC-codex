"""
Local account authentication: register / login / logout / current-user.

Self-contained username + password auth backed by the local database. No external
identity provider. On successful register/login a locally-signed JWT is returned
and also set as the `arena_token` cookie.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from api.auth_dependencies import (
    AUTH_ENABLED,
    AUTH_TOKEN_TTL_DAYS,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database.connection import get_db
from database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Accepts a plain username (3-50 chars) or an email address.
_USERNAME_RE = re.compile(
    r"^(?:[A-Za-z0-9_.\-]{3,50}|[A-Za-z0-9_.+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63})+)$"
)
_COOKIE_MAX_AGE = AUTH_TOKEN_TTL_DAYS * 24 * 3600


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str) -> str:
        v = (v or "").strip()
        if not _USERNAME_RE.match(v):
            raise ValueError("用户名需为 3-50 个字符(字母、数字、_ . -)或邮箱格式")
        return v

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError("密码至少需要 6 个字符")
        if len(v) > 128:
            raise ValueError("密码过长")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


def _user_public(user: User) -> dict:
    return {"id": user.id, "username": user.username, "email": user.email}


def _set_token_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="arena_token",
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=False,  # frontend reads it via js-cookie and sends it as a Bearer header
        samesite="lax",
        path="/",
    )


@router.get("/config")
def auth_config() -> dict:
    """Tell the frontend whether login is required (local auth) or disabled."""
    return {"auth_enabled": AUTH_ENABLED, "mode": "local"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    if not AUTH_ENABLED:
        raise HTTPException(status_code=400, detail="认证功能已关闭")

    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="该用户名/邮箱已被注册")

    user = User(
        username=payload.username,
        email=None,
        password_hash=hash_password(payload.password),
        is_active="true",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    _set_token_cookie(response, token)
    logger.info("New local user registered: %s", user.username)
    return {"access_token": token, "token_type": "bearer", "user": _user_public(user)}


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    if not AUTH_ENABLED:
        raise HTTPException(status_code=400, detail="认证功能已关闭")

    user = db.query(User).filter(User.username == (payload.username or "").strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.is_active != "true":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    token = create_access_token(user)
    _set_token_cookie(response, token)
    return {"access_token": token, "token_type": "bearer", "user": _user_public(user)}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key="arena_token", path="/")
    return {"ok": True}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return _user_public(current_user)
