"""
Binance Futures Management API Routes

Provides endpoints for:
- Wallet setup and configuration (API key binding)
- Balance and position queries
- Manual order placement
- Connection testing

This package splits the former single ``binance_routes`` module by concern.
The shared ``router`` instance lives in ``_shared``; importing the endpoint
modules below attaches their route decorators to it.
"""
from ._shared import (
    router,
    logger,
    _client_cache,
    _get_client,
    _clear_client_cache,
    _is_premium_user,
    _format_credential_error,
    DAILY_QUOTA_LIMIT,
)

# Import endpoint modules for their side effect of registering routes.
from . import wallet  # noqa: E402,F401
from . import trading  # noqa: E402,F401
from . import account  # noqa: E402,F401
from . import market  # noqa: E402,F401

# Re-export request models for backward compatibility.
from .wallet import BinanceSetupRequest, ConfirmLimitedBindingRequest  # noqa: E402,F401
from .trading import ManualOrderRequest, TestnetOrderProbeRequest  # noqa: E402,F401
from .market import BinanceSymbolSelectionRequest  # noqa: E402,F401

__all__ = [
    "router",
    "logger",
    "_client_cache",
    "_get_client",
    "_clear_client_cache",
    "_is_premium_user",
    "_format_credential_error",
    "DAILY_QUOTA_LIMIT",
    "BinanceSetupRequest",
    "ConfirmLimitedBindingRequest",
    "ManualOrderRequest",
    "TestnetOrderProbeRequest",
    "BinanceSymbolSelectionRequest",
]
