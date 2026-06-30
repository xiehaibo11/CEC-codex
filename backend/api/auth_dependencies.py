"""
Authentication and authorization dependencies for business API routes.

Local-first auth: users register/login with a username + password stored in the
local database (PBKDF2-hashed). On login the backend issues a locally-signed JWT
(HS256) that is presented back as a Bearer header or `arena_token` cookie. No
external identity provider is required.

Set AUTH_ENABLED=false to disable auth entirely and serve everything as a single
shared local user (handy for pure single-user/local runs).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User

logger = logging.getLogger(__name__)

# Whether login is required. Default true: the app uses local account
# registration + login. Set AUTH_ENABLED=false to run with no login (every
# request is served as the shared local "default" user).
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
DEFAULT_LOCAL_USERNAME = "default"

# Secret used to sign local JWTs. MUST be set to a stable random value in
# production (otherwise all sessions are invalidated on restart / are insecure).
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "").strip()
if not AUTH_SECRET_KEY:
    AUTH_SECRET_KEY = "dev-insecure-secret-change-me"
    if AUTH_ENABLED:
        logger.warning(
            "AUTH_SECRET_KEY is not set; using an insecure development default. "
            "Set AUTH_SECRET_KEY to a strong random value for any real deployment."
        )

AUTH_JWT_ALGORITHM = "HS256"
AUTH_TOKEN_TTL_DAYS = int(os.getenv("AUTH_TOKEN_TTL_DAYS", "30"))

# Password hashing (PBKDF2-HMAC-SHA256, stdlib only — no extra deps).
_PBKDF2_ITERATIONS = 200_000
_PBKDF2_ALGO = "sha256"


def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2 hash: pbkdf2_sha256$iterations$salt$hash."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO, password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time verification of a password against a stored PBKDF2 hash."""
    if not stored:
        return False
    try:
        scheme, iterations, salt, digest = stored.split("$", 3)
    except ValueError:
        return False
    if not scheme.startswith("pbkdf2_"):
        return False
    algo = scheme.split("_", 1)[1]
    try:
        computed = hashlib.pbkdf2_hmac(
            algo, password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed, digest)


def create_access_token(user: User) -> str:
    """Issue a locally-signed JWT for the given user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=AUTH_TOKEN_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, AUTH_SECRET_KEY, algorithm=AUTH_JWT_ALGORITHM)


def _verify_local_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            AUTH_SECRET_KEY,
            algorithms=[AUTH_JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except InvalidTokenError as exc:
        logger.info("Local token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _get_or_create_local_user(db: Session) -> User:
    """Return the shared local user used when authentication is disabled."""
    user = db.query(User).filter(User.username == DEFAULT_LOCAL_USERNAME).first()
    if user:
        return user
    user = User(username=DEFAULT_LOCAL_USERNAME, email=None, password_hash=None, is_active="true")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.cookies.get("arena_token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # No-auth mode: serve everyone as the shared local user.
    if not AUTH_ENABLED:
        return _get_or_create_local_user(db)

    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _verify_local_token(token)
    try:
        user_id = int(claims["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.is_active != "true":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_account_for_current_user(
    account_id: int,
    current_user: User,
    db: Session,
    *,
    active_only: bool = True,
):
    from database.models import Account

    query = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id)
    if active_only:
        query = query.filter(Account.is_active == "true")
    query = query.filter(Account.is_deleted != True)

    account = query.first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def require_path_account_owner(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Route dependency that protects endpoints with an account_id path param."""
    raw_account_id = request.path_params.get("account_id")
    if raw_account_id is not None:
        try:
            account_id = int(raw_account_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc
        get_account_for_current_user(account_id, current_user, db, active_only=False)
    return current_user
