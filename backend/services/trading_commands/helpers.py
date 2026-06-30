"""
Trading Commands - shared helpers, constants, and pricing/quota utilities.

This module holds the cohesive helper layer used by the AI-trade dispatchers
and the exchange-specific order modules. No routing or order-placement logic
lives here.
"""
import logging
from decimal import Decimal
from typing import Dict, Tuple, List, Any

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from database.models import (
    CRYPTO_MIN_COMMISSION,
    CRYPTO_COMMISSION_RATE,
    AIDecisionLog,
    ProgramExecutionLog,
)
from services.market_data import get_last_price
from services.ai_decision_service import SUPPORTED_SYMBOLS
from config.settings import BINANCE_DAILY_QUOTA_LIMIT


logger = logging.getLogger(__name__)

AI_TRADING_SYMBOLS: List[str] = ["BTC"]  # Paper trading deprecated, keep minimal
ORACLE_PRICE_DEVIATION_LIMIT_PERCENT = 1.0


def _is_premium_user(db: Session) -> bool:
    """Membership removed: all features unlocked for self-hosted use."""
    return True


def _check_binance_daily_quota(db: Session, account_id: int) -> Tuple[bool, Dict[str, int]]:
    """
    Check if Binance mainnet daily quota is exceeded for an account.

    Returns:
        Tuple of (exceeded: bool, info: dict with used/limit/remaining)
    """
    # Check premium status first
    if _is_premium_user(db):
        return False, {"used": 0, "limit": BINANCE_DAILY_QUOTA_LIMIT, "remaining": BINANCE_DAILY_QUOTA_LIMIT}

    # Use UTC midnight for quota reset
    today_start_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Count AIDecisionLog entries (only actual trades: buy/sell/close)
    ai_count = db.query(func.count(AIDecisionLog.id)).filter(
        AIDecisionLog.account_id == account_id,
        AIDecisionLog.exchange == "binance",
        AIDecisionLog.hyperliquid_environment == "mainnet",
        AIDecisionLog.created_at >= today_start_utc,
        AIDecisionLog.operation.in_(["buy", "sell", "close"]),
    ).scalar() or 0

    # Count ProgramExecutionLog entries (only actual trades: buy/sell/close)
    program_count = db.query(func.count(ProgramExecutionLog.id)).filter(
        ProgramExecutionLog.account_id == account_id,
        ProgramExecutionLog.exchange == "binance",
        ProgramExecutionLog.environment == "mainnet",
        ProgramExecutionLog.created_at >= today_start_utc,
        ProgramExecutionLog.decision_action.in_(["buy", "sell", "close"]),
    ).scalar() or 0

    used = ai_count + program_count
    remaining = max(0, BINANCE_DAILY_QUOTA_LIMIT - used)
    exceeded = used >= BINANCE_DAILY_QUOTA_LIMIT

    return exceeded, {"used": used, "limit": BINANCE_DAILY_QUOTA_LIMIT, "remaining": remaining}


def _enforce_price_bounds(
    *,
    symbol: str,
    account_name: str,
    operation: str,
    current_price: float,
    requested_price: float,
) -> Tuple[float, float, bool]:
    """Clamp requested price into ±1% oracle window and log adjustments."""

    if current_price <= 0 or requested_price <= 0:
        return requested_price, 0.0, False

    limit = ORACLE_PRICE_DEVIATION_LIMIT_PERCENT / 100
    lower_bound = current_price * (1 - limit)
    upper_bound = current_price * (1 + limit)

    clamped_price = max(min(requested_price, upper_bound), lower_bound)
    deviation_percent = abs(requested_price - current_price) / current_price * 100
    was_adjusted = clamped_price != requested_price

    if was_adjusted:
        logger.warning(
            f"[AI COMPLIANCE] {operation.upper()} {symbol} price from AI for {account_name} "
            f"violates Hyperliquid ±1% rule. market=${current_price:.2f}, "
            f"requested=${requested_price:.2f}, deviation={deviation_percent:.2f}%. "
            f"Adjusted to ${clamped_price:.2f}."
        )

    return clamped_price, deviation_percent, was_adjusted


def _get_symbol_name(symbol: str) -> str:
    return SUPPORTED_SYMBOLS.get(symbol, symbol)


def _estimate_buy_cash_needed(price: float, quantity: float) -> Decimal:
    """Estimate cash required for a BUY including commission."""
    notional = Decimal(str(price)) * Decimal(str(quantity))
    commission = max(
        notional * Decimal(str(CRYPTO_COMMISSION_RATE)),
        Decimal(str(CRYPTO_MIN_COMMISSION)),
    )
    return notional + commission


def _get_market_prices(symbols: List[str]) -> Dict[str, float]:
    """Get latest prices for given symbols"""
    prices = {}
    for symbol in symbols:
        try:
            price = float(get_last_price(symbol, "CRYPTO"))
            if price > 0:
                prices[symbol] = price
        except Exception as err:
            logger.warning(f"Failed to get price for {symbol}: {err}")
    return prices


def _get_realtime_ticker_snapshot(symbols: List[str], environment: str = "mainnet") -> Dict[str, Dict[str, Any]]:
    """Get a realtime ticker snapshot for prompt generation and price alignment."""
    from services.market_data import get_ticker_data

    tickers: Dict[str, Dict[str, Any]] = {}
    for symbol in symbols:
        try:
            ticker = get_ticker_data(symbol, "CRYPTO", environment)
            if ticker and float(ticker.get("price", 0) or 0) > 0:
                tickers[symbol] = ticker
        except Exception as err:
            logger.warning(f"Failed to get realtime ticker for {symbol}: {err}")
    return tickers
