"""
Signal Detection Service - state dataclasses and module helpers.

Detects signal triggers based on market flow data.
Uses edge-triggered logic: only triggers when condition changes from False to True.
"""

import json
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _get_market_regime_for_trigger(symbol: str, timeframe: str = "5m") -> Optional[str]:
    """Get market regime classification for a trigger and return as JSON string.

    Args:
        symbol: Trading symbol (e.g., "BTC")
        timeframe: Time window for regime calculation (e.g., "5m", "15m", "1h")

    Returns:
        JSON string with regime, direction, confidence, reason, timeframe, and indicators
    """
    try:
        from database.connection import SessionLocal
        from services.market_regime_service import get_market_regime
        from datetime import datetime

        db = SessionLocal()
        try:
            # FIX: Pass current timestamp and use_realtime=True to fetch current K-line from API
            # This ensures regime calculation uses the latest market data including unfinished candles
            timestamp_ms = int(datetime.utcnow().timestamp() * 1000)
            result = get_market_regime(
                db, symbol, timeframe,
                timestamp_ms=timestamp_ms,
                use_realtime=True
            )
            return json.dumps({
                "symbol": symbol,
                "timeframe": timeframe,
                "regime": result.get("regime"),
                "direction": result.get("direction"),
                "confidence": result.get("confidence"),
                "reason": result.get("reason"),
                "indicators": result.get("indicators", {}),
            })
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to get market regime for {symbol}/{timeframe}: {e}")
        return None


@dataclass
class SignalState:
    """Track the active state of a signal for edge detection"""
    signal_id: int
    symbol: str
    is_active: bool = False
    last_value: Optional[float] = None
    last_check_time: float = 0


@dataclass
class PoolState:
    """Track the active state of a signal pool for edge detection"""
    pool_id: int
    symbol: str
    is_active: bool = False
    last_check_time: float = 0
    # Track which signals in the pool are currently meeting their conditions
    signal_conditions_met: Dict[int, bool] = field(default_factory=dict)
