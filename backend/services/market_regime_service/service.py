"""
Market regime orchestration entry point.

Wires flow indicators, price metrics, classification, and confidence scoring
together via the public get_market_regime() entry point.
"""

import math
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from database.models import MarketRegimeConfig
from services.market_flow_indicators import get_flow_indicators_for_prompt, TIMEFRAME_MS

from services.market_regime_service.data import (
    fetch_kline_data,
    calculate_price_metrics,
)
from services.market_regime_service.classification import (
    REGIME_NOISE,
    DIRECTION_NEUTRAL,
    get_default_config,
    calculate_direction,
    calculate_confidence,
    calculate_pattern_penalty,
    calculate_direction_penalty,
    classify_regime,
)

logger = logging.getLogger(__name__)


def get_market_regime(
    db: Session,
    symbol: str,
    timeframe: str = "5m",
    config_id: Optional[int] = None,
    timestamp_ms: Optional[int] = None,
    use_realtime: bool = False,
    exchange: str = "hyperliquid"
) -> Dict[str, Any]:
    """
    Main entry point: Get market regime classification for a symbol.

    IMPORTANT: This function reuses market_flow_indicators service for CVD, Taker, OI
    to ensure consistency with signal detection system.

    Args:
        db: Database session
        symbol: Trading pair symbol (e.g., "BTC")
        timeframe: Time frame (1m, 5m, 15m, 1h, etc.)
        config_id: Optional config ID, uses default if not specified
        timestamp_ms: Optional timestamp for historical queries (backtesting)
        use_realtime: If True, fetch current K-line from API for real-time triggers
        exchange: Exchange to use for data ("hyperliquid" or "binance")

    Returns:
        Dict with regime, direction, confidence, reason, indicators, and debug info
    """
    # Get config
    if config_id:
        config = db.query(MarketRegimeConfig).filter(
            MarketRegimeConfig.id == config_id
        ).first()
    else:
        config = get_default_config(db)

    if not config:
        return {
            "regime": REGIME_NOISE,
            "direction": DIRECTION_NEUTRAL,
            "confidence": 0.0,
            "reason": "No regime config found",
            "indicators": {},
            "debug": {}
        }

    # Validate timeframe
    if timeframe not in TIMEFRAME_MS:
        return {
            "regime": REGIME_NOISE,
            "direction": DIRECTION_NEUTRAL,
            "confidence": 0.0,
            "reason": f"Unsupported timeframe: {timeframe}",
            "indicators": {},
            "debug": {}
        }

    # Get current time if not specified
    if timestamp_ms is None:
        timestamp_ms = int(datetime.utcnow().timestamp() * 1000)

    # Fetch flow indicators using market_flow_indicators service (REUSE!)
    flow_data = get_flow_indicators_for_prompt(
        db, symbol, timeframe, ["CVD", "TAKER", "OI_DELTA"], timestamp_ms,
        exchange=exchange
    )

    cvd_data = flow_data.get("CVD")
    taker_data = flow_data.get("TAKER")
    oi_delta_data = flow_data.get("OI_DELTA")

    # Check if we have enough data
    if not cvd_data or not taker_data:
        return {
            "regime": REGIME_NOISE,
            "direction": DIRECTION_NEUTRAL,
            "confidence": 0.0,
            "reason": "Insufficient market flow data",
            "indicators": {},
            "debug": {"cvd_data": cvd_data, "taker_data": taker_data}
        }

    # Extract indicator values
    # CVD ratio: current CVD / total notional (buy + sell)
    cvd_current = cvd_data.get("current", 0) or 0
    taker_buy = taker_data.get("buy", 0)
    taker_sell = taker_data.get("sell", 0)
    total_notional = taker_buy + taker_sell

    cvd_ratio = cvd_current / total_notional if total_notional > 0 else 0.0

    # Taker log ratio: ln(buy/sell) for symmetry around 0
    if taker_buy > 0 and taker_sell > 0:
        taker_log_ratio = math.log(taker_buy / taker_sell)
    else:
        taker_log_ratio = 0.0

    # OI delta: percentage change
    oi_delta = oi_delta_data.get("current", 0) if oi_delta_data else 0.0

    # Fetch K-line data and calculate price metrics (ATR, RSI)
    kline_data = fetch_kline_data(
        db, symbol, timeframe, limit=50,
        current_time_ms=timestamp_ms, use_realtime=use_realtime,
        exchange=exchange
    )
    price_metrics = calculate_price_metrics(kline_data)
    price_atr = price_metrics["price_atr"]
    price_range_atr = price_metrics["price_range_atr"]
    rsi = price_metrics["rsi"]

    # Classify regime
    regime, reason = classify_regime(
        cvd_ratio, taker_log_ratio, oi_delta, price_atr, rsi, price_range_atr, config
    )

    # Calculate direction and confidence
    direction = calculate_direction(cvd_ratio, taker_log_ratio, price_atr)
    base_confidence = calculate_confidence(cvd_ratio, taker_log_ratio, oi_delta, price_atr)

    # Apply penalty multipliers for regime-specific quality assessment
    pattern_penalty = calculate_pattern_penalty(
        regime, cvd_ratio, price_atr, oi_delta, rsi, price_range_atr
    )
    direction_penalty = calculate_direction_penalty(
        regime, cvd_ratio, price_atr, taker_log_ratio
    )
    confidence = base_confidence * pattern_penalty * direction_penalty

    return {
        "regime": regime,
        "direction": direction,
        "confidence": round(confidence, 3),
        "reason": reason,
        "indicators": {
            "cvd_ratio": round(cvd_ratio, 4),  # CVD / Total Notional
            "oi_delta": round(oi_delta, 3),    # OI change percentage
            "taker_ratio": round(math.exp(taker_log_ratio), 3),  # buy/sell ratio
            "price_atr": round(price_atr, 3),
            "rsi": round(rsi, 1)
        },
        "debug": {
            "cvd_ratio": round(cvd_ratio, 4),
            "taker_log_ratio": round(taker_log_ratio, 4),
            "oi_delta_pct": round(oi_delta, 3),
            "taker_buy": round(taker_buy, 2),
            "taker_sell": round(taker_sell, 2),
            "total_notional": round(total_notional, 2),
            "timestamp_ms": timestamp_ms,
            "timeframe": timeframe
        }
    }
