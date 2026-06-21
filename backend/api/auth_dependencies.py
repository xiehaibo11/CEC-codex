"""
Authentication and authorization dependencies for business API routes.

Casdoor issues standard OIDC/JWT tokens. We verify tokens against the
provider JWKS and map each external subject to an isolated local user.
"""

from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import InvalidTokenError, PyJWKClient
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Account, User

logger = logging.getLogger(__name__)

AUTH_PROVIDER = os.getenv("AUTH_PROVIDER") or os.getenv("AUTH_PROXY_UPSTREAM", "https://auth.bocail.com")
AUTH_ISSUER = os.getenv("AUTH_ISSUER", AUTH_PROVIDER.rstrip("/"))
AUTH_CLIENT_ID = os.getenv("AUTH_CLIENT_ID", "").strip()
AUTH_JWKS_URL = os.getenv("AUTH_JWKS_URL", f"{AUTH_ISSUER}/.well-known/jwks")
AUTH_ALGORITHMS = ["RS256", "RS512", "ES256", "ES384", "ES512"]


@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    return PyJWKClient(AUTH_JWKS_URL)


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.cookies.get("arena_token")


def _external_subject(claims: dict[str, Any]) -> str:
    subject = claims.get("sub")
    if subject:
        return str(subject)

    owner = claims.get("owner")
    name = claims.get("name") or claims.get("id") or claims.get("email")
    if owner and name:
        return f"{owner}/{name}"
    if name:
        return str(name)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authenticated token is missing a stable user subject",
    )


def _local_username_from_claims(claims: dict[str, Any]) -> str:
    digest = hashlib.sha256(_external_subject(claims).encode("utf-8")).hexdigest()[:32]
    return f"casdoor_{digest}"


def _verify_casdoor_token(token: str) -> dict[str, Any]:
    if not AUTH_CLIENT_ID or AUTH_CLIENT_ID == "your-casdoor-application-client-id":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_CLIENT_ID is not configured; refusing to accept unscoped login tokens",
        )

    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=AUTH_ALGORITHMS,
            audience=AUTH_CLIENT_ID,
            issuer=AUTH_ISSUER,
            options={"require": ["exp", "iat"]},
            leeway=30,
        )
    except InvalidTokenError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("JWT validation infrastructure failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider verification is temporarily unavailable",
        ) from exc


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _verify_casdoor_token(token)
    username = _local_username_from_claims(claims)
    email = claims.get("email")

    user = db.query(User).filter(User.username == username).first()
    if user:
        if email and user.email != email:
            user.email = email
            db.commit()
            db.refresh(user)
        return user

    user = User(username=username, email=email, is_active="true")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_account_for_current_user(
    account_id: int,
    current_user: User,
    db: Session,
    *,
    active_only: bool = True,
) -> Account:
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
