"""
Trading Commands Service - Handles order execution and trading logic.

This package was split from a single ``trading_commands.py`` module by
responsibility. All public symbols remain importable from
``services.trading_commands`` exactly as before:

- helpers          : shared constants, pricing/quota helpers
- crypto_orders    : generic AI-trade dispatcher + legacy random trading
- hyperliquid_orders : Hyperliquid AI-driven order placement
- binance_orders   : Binance AI-driven order placement
"""

from .helpers import (
    AI_TRADING_SYMBOLS,
    ORACLE_PRICE_DEVIATION_LIMIT_PERCENT,
    _is_premium_user,
    _check_binance_daily_quota,
    _enforce_price_bounds,
    _get_symbol_name,
    _estimate_buy_cash_needed,
    _get_market_prices,
    _get_realtime_ticker_snapshot,
)
from .hyperliquid_orders import (
    test_hyperliquid_function,
    place_ai_driven_hyperliquid_order,
    HYPERLIQUID_TRADE_JOB_ID,
)
from .crypto_orders import (
    _select_side,
    place_ai_driven_crypto_order,
    place_random_crypto_order,
    AUTO_TRADE_JOB_ID,
    AI_TRADE_JOB_ID,
)
from .binance_orders import (
    place_ai_driven_binance_order,
    _execute_binance_decision,
    BINANCE_TRADE_JOB_ID,
)

__all__ = [
    "AI_TRADING_SYMBOLS",
    "ORACLE_PRICE_DEVIATION_LIMIT_PERCENT",
    "_is_premium_user",
    "_check_binance_daily_quota",
    "_enforce_price_bounds",
    "_get_symbol_name",
    "_estimate_buy_cash_needed",
    "_get_market_prices",
    "_get_realtime_ticker_snapshot",
    "_select_side",
    "place_ai_driven_crypto_order",
    "place_random_crypto_order",
    "AUTO_TRADE_JOB_ID",
    "AI_TRADE_JOB_ID",
    "test_hyperliquid_function",
    "place_ai_driven_hyperliquid_order",
    "HYPERLIQUID_TRADE_JOB_ID",
    "place_ai_driven_binance_order",
    "_execute_binance_decision",
    "BINANCE_TRADE_JOB_ID",
]
