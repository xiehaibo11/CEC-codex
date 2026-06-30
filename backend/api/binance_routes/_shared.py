"""
Shared state and helpers for Binance Futures Management API routes.

Defines the single shared APIRouter instance, the trading-client cache,
credential-error formatting, premium gating, and the daily-quota constant.
Endpoint modules import `router` from here and attach their decorators.
"""
from fastapi import APIRouter
from sqlalchemy.orm import Session
import logging

from database.models import BinanceWallet
from utils.encryption import decrypt_private_key
from services.binance_trading_client import BinanceTradingClient
from config.settings import BINANCE_DAILY_QUOTA_LIMIT, BINANCE_SERVER_EGRESS_IP

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/binance", tags=["binance"])

# Client cache for reuse
_client_cache: dict = {}


def _get_client(wallet: BinanceWallet) -> BinanceTradingClient:
    """Get or create trading client for a wallet"""
    cache_key = f"{wallet.account_id}_{wallet.environment}"
    if cache_key not in _client_cache:
        api_key = decrypt_private_key(wallet.api_key_encrypted)
        secret_key = decrypt_private_key(wallet.secret_key_encrypted)
        _client_cache[cache_key] = BinanceTradingClient(
            api_key=api_key,
            secret_key=secret_key,
            environment=wallet.environment
        )
    return _client_cache[cache_key]


def _clear_client_cache(account_id: int = None, environment: str = None):
    """Clear client cache"""
    if account_id and environment:
        cache_key = f"{account_id}_{environment}"
        _client_cache.pop(cache_key, None)
    else:
        _client_cache.clear()


def _is_premium_user(db: Session) -> bool:
    """Membership removed: all features unlocked for self-hosted use."""
    return True


# Daily quota uses centralized config
DAILY_QUOTA_LIMIT = BINANCE_DAILY_QUOTA_LIMIT


def _format_credential_error(environment: str, error: Exception) -> str:
    """Return a user-actionable Binance credential validation error."""
    raw_message = str(error)
    code = getattr(error, "code", None)
    message = getattr(error, "message", raw_message)
    server_ip_hint = (
        f" If IP restrictions are enabled on the API key, whitelist this server IP: {BINANCE_SERVER_EGRESS_IP}."
        if BINANCE_SERVER_EGRESS_IP
        else " If IP restrictions are enabled on the API key, whitelist this server's outbound IP."
    )

    if str(code) == "-2015" or "-2015" in raw_message:
        if environment == "testnet":
            return (
                "Binance rejected this Testnet API key (-2015). The Testnet/Demo panel "
                "cannot use a Mainnet API key. Use an API key created in Binance Futures "
                "Demo Trading for the Testnet panel; Mainnet, Spot Testnet, or old Mock "
                "Trading keys will be rejected. Make sure USD-M Futures API "
                f"read/trading permissions are enabled.{server_ip_hint} Original Binance message: {message}"
            )

        return (
            "Binance rejected this Mainnet API key (-2015). Use a Binance USD-M Futures "
            "Mainnet API key, enable Futures read/trading permissions, and confirm the "
            f"key is saved in the Mainnet panel.{server_ip_hint} Original Binance message: {message}"
        )

    if str(code) == "-1021" or "-1021" in raw_message:
        return (
            "Binance rejected the request because the server timestamp was outside recvWindow. "
            "The system retried after time sync; please try again in a moment. "
            f"Original Binance message: {message}"
        )

    return f"Unable to validate Binance {environment} credentials: {raw_message}"
