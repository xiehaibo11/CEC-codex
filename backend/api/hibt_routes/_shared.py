"""Shared state and helpers for HiBT Futures API routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from database.models import HibtWallet
from services.hibt_trading_client import HibtAPIError, HibtTradingClient
from utils.encryption import decrypt_private_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hibt", tags=["hibt"])

_client_cache: dict[str, HibtTradingClient] = {}


def _resolve_wallet(db: Session, account_id: int, environment: str) -> HibtWallet:
    """Return the active HiBT wallet for an account/environment or 404."""
    wallet = db.query(HibtWallet).filter(
        HibtWallet.account_id == account_id,
        HibtWallet.environment == environment,
        HibtWallet.is_active == "true",
    ).first()
    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} HiBT wallet configured")
    return wallet


def _get_client(wallet: HibtWallet) -> HibtTradingClient:
    """Get or create HiBT trading client for a wallet."""
    cache_key = f"{wallet.account_id}_{wallet.environment}"
    if cache_key not in _client_cache:
        access_key = decrypt_private_key(wallet.access_key_encrypted)
        secret_key = decrypt_private_key(wallet.secret_key_encrypted)
        _client_cache[cache_key] = HibtTradingClient(
            access_key=access_key,
            secret_key=secret_key,
            environment=wallet.environment,
        )
    return _client_cache[cache_key]


def _clear_client_cache(account_id: int | None = None, environment: str | None = None) -> None:
    """Clear cached HiBT clients."""
    if account_id and environment:
        _client_cache.pop(f"{account_id}_{environment}", None)
        return
    _client_cache.clear()


def _format_credential_error(environment: str, error: Exception) -> str:
    """Return a user-actionable HiBT credential validation error."""
    raw_message = str(error)
    code = getattr(error, "code", None)
    message = getattr(error, "message", raw_message)

    if isinstance(error, HibtAPIError):
        if str(code) in {"220004", "210021"}:
            return f"HiBT rejected this {environment} Access Key. Confirm it belongs to the HiBT perpetual API and has query permission. Original message: {message}"
        if str(code) == "220008":
            return f"HiBT signature verification failed. Check the Secret Key copied during API creation. Original message: {message}"
        if str(code) == "220012":
            return f"HiBT rejected the server IP whitelist. If IP restrictions are enabled, add this server's outbound IP. Original message: {message}"
        if str(code) in {"220013", "210020"}:
            return f"HiBT API key has no query permission. Enable query permission for this key. Original message: {message}"
        if str(code) == "220014":
            return f"HiBT API key has no trading permission. Query works, but order endpoints will fail until trading permission is enabled. Original message: {message}"

    return f"Unable to validate HiBT {environment} credentials: {raw_message}"
