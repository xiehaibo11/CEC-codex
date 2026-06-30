#!/usr/bin/env python3
"""
Indicator dispatch / aggregation for AI prompt variables.

Public entry points that route an indicator name to its per-metric fetch
helper: get_indicator_value (single value for signal detection) and
get_flow_indicators_for_prompt (batch fetch for prompt injection).
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from services.market_flow_indicators.common import TIMEFRAME_MS
from services.market_flow_indicators.trade_indicators import (
    _get_cvd_data,
    _get_taker_data,
    _get_price_change_data,
    _get_volatility_data,
)
from services.market_flow_indicators.metric_indicators import (
    _get_oi_data,
    _get_oi_delta_data,
    _get_funding_data,
)
from services.market_flow_indicators.orderbook_indicators import (
    _get_depth_data,
    _get_imbalance_data,
)

logger = logging.getLogger(__name__)


def get_indicator_value(
    db: Session,
    symbol: str,
    indicator: str,
    period: str,
    current_time_ms: Optional[int] = None,
    exchange: str = "hyperliquid"
) -> Optional[float]:
    """
    Get a single indicator's current value for signal detection.

    This is the canonical function for retrieving indicator values.
    Use this for signal detection, alerts, and any feature that needs
    a single numeric value.

    Args:
        db: Database session
        symbol: Trading symbol (e.g., "BTC")
        indicator: Indicator type - one of:
            - "OI_DELTA": Open Interest change percentage
            - "CVD": Cumulative Volume Delta
            - "DEPTH": Order book depth ratio (bid/ask)
            - "IMBALANCE": Order book imbalance (-1 to 1)
            - "TAKER": Taker buy/sell ratio
        period: Time period (e.g., "1m", "5m", "15m", "1h")
        current_time_ms: Current timestamp in ms (defaults to now)
        exchange: Exchange name (e.g., "hyperliquid", "binance")

    Returns:
        Current value as float, or None if data unavailable
    """
    if period not in TIMEFRAME_MS:
        logger.warning(f"Unsupported period: {period}")
        return None

    interval_ms = TIMEFRAME_MS[period]

    if current_time_ms is None:
        from datetime import datetime
        current_time_ms = int(datetime.utcnow().timestamp() * 1000)

    indicator_upper = indicator.upper()

    try:
        if indicator_upper == "OI_DELTA":
            data = _get_oi_delta_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("current") if data else None
        elif indicator_upper == "CVD":
            data = _get_cvd_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("current") if data else None
        elif indicator_upper == "DEPTH":
            data = _get_depth_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("ratio") if data else None
        elif indicator_upper == "IMBALANCE":
            data = _get_imbalance_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("current") if data else None
        elif indicator_upper == "TAKER":
            data = _get_taker_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("ratio") if data else None
        elif indicator_upper == "OI":
            data = _get_oi_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("current") if data else None
        elif indicator_upper == "FUNDING":
            data = _get_funding_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("change") if data else None  # Return change in bps
        elif indicator_upper == "PRICE_CHANGE":
            data = _get_price_change_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("current") if data else None
        elif indicator_upper == "VOLATILITY":
            data = _get_volatility_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            return data.get("current") if data else None
        else:
            logger.warning(f"Unknown indicator: {indicator}")
            return None
    except Exception as e:
        logger.error(f"Error getting indicator {indicator} for {symbol}: {e}")
        return None


def get_flow_indicators_for_prompt(
    db: Session,
    symbol: str,
    period: str,
    indicators: List[str],
    current_time_ms: Optional[int] = None,
    exchange: str = "hyperliquid"
) -> Dict[str, Any]:
    """
    Get market flow indicator data formatted for AI prompt injection.

    Args:
        db: Database session
        symbol: Trading symbol (e.g., "BTC")
        period: Time period (e.g., "15m", "1h")
        indicators: List of indicators to calculate ["CVD", "TAKER", "OI", "FUNDING", "DEPTH"]
        current_time_ms: Current timestamp in ms (defaults to now)
        exchange: Exchange name (e.g., "hyperliquid", "binance")

    Returns:
        Dict with indicator name as key and raw data dict as value
    """
    if period not in TIMEFRAME_MS:
        logger.warning(f"Unsupported period: {period}")
        return {}

    interval_ms = TIMEFRAME_MS[period]

    if current_time_ms is None:
        from datetime import datetime
        current_time_ms = int(datetime.utcnow().timestamp() * 1000)

    results = {}

    for indicator in indicators:
        indicator_upper = indicator.upper()
        try:
            if indicator_upper == "CVD":
                results["CVD"] = _get_cvd_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "TAKER":
                results["TAKER"] = _get_taker_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "OI":
                results["OI"] = _get_oi_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "OI_DELTA":
                results["OI_DELTA"] = _get_oi_delta_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "FUNDING":
                results["FUNDING"] = _get_funding_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "DEPTH":
                results["DEPTH"] = _get_depth_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "IMBALANCE":
                results["IMBALANCE"] = _get_imbalance_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "PRICE_CHANGE":
                results["PRICE_CHANGE"] = _get_price_change_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            elif indicator_upper == "VOLATILITY":
                results["VOLATILITY"] = _get_volatility_data(db, symbol, period, interval_ms, current_time_ms, exchange)
            else:
                logger.warning(f"Unknown flow indicator: {indicator}")
        except Exception as e:
            logger.error(f"Error calculating flow indicator {indicator}: {e}")
            results[indicator_upper] = None

    return results
