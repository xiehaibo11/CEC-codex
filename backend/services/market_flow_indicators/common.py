#!/usr/bin/env python3
"""
Shared helpers and constants for Market Flow Indicators.

Leaf module: time helpers, value formatting, the timeframe mapping, and the
insufficient-data warning throttle. Indicator submodules import from here.
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)
INSUFFICIENT_DATA_WARNING_COOLDOWN_SECONDS = 600
_insufficient_data_lock = threading.Lock()
_insufficient_data_warning_at: dict[str, float] = {}


def _log_insufficient_data_once(key: str, message: str) -> None:
    now = time.time()
    with _insufficient_data_lock:
        last_warning_at = _insufficient_data_warning_at.get(key, 0.0)
        if now - last_warning_at < INSUFFICIENT_DATA_WARNING_COOLDOWN_SECONDS:
            logger.debug(message)
            return
        _insufficient_data_warning_at[key] = now
    logger.warning(message)

# Timeframe to milliseconds mapping
TIMEFRAME_MS = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "8h": 8 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


def floor_timestamp(ts_ms: int, interval_ms: int) -> int:
    """Floor timestamp to interval boundary"""
    return (ts_ms // interval_ms) * interval_ms


def decimal_to_float(val) -> Optional[float]:
    """Convert Decimal to float, handling None"""
    if val is None:
        return None
    return float(val)


def format_volume(value: float) -> str:
    """Format volume with appropriate unit (K, M, B)"""
    abs_val = abs(value)
    sign = "+" if value >= 0 else "-"
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val/1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}${abs_val/1_000_000:.2f}M"
    elif abs_val >= 1_000:
        return f"{sign}${abs_val/1_000:.2f}K"
    else:
        return f"{sign}${abs_val:.2f}"
