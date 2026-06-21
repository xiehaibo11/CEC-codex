"""Shared K-line and prediction-window settings for the factor engine."""

from typing import Dict, List


FORWARD_PERIOD_SECONDS: Dict[str, int] = {
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "12h": 12 * 60 * 60,
    "24h": 24 * 60 * 60,
}

PERIOD_SECONDS: Dict[str, int] = {
    "1m": 60,
    "3m": 3 * 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
    "6h": 6 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "1d": 24 * 60 * 60,
    "3d": 3 * 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
    "1M": 30 * 24 * 60 * 60,
}

HYPERLIQUID_FACTOR_KLINE_PERIODS: List[str] = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]

BINANCE_FACTOR_KLINE_PERIODS: List[str] = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]


def get_supported_factor_periods(exchange: str) -> List[str]:
    """Return K-line periods supported by the factor engine for an exchange."""
    if exchange == "binance":
        return BINANCE_FACTOR_KLINE_PERIODS
    return HYPERLIQUID_FACTOR_KLINE_PERIODS


def period_to_seconds(period: str) -> int:
    """Convert a K-line period label to seconds."""
    return PERIOD_SECONDS.get(period, 60 * 60)


def get_forward_period_offsets(period: str) -> Dict[str, int]:
    """Map prediction windows to forward bar offsets for a K-line period.

    The prediction windows are real clock horizons. For example:
    5m K-line + 1h prediction window = 12 forward bars.
    4h K-line + 24h prediction window = 6 forward bars.
    Windows that cannot be represented exactly by the K-line period are skipped.
    """
    period_seconds = period_to_seconds(period)
    offsets: Dict[str, int] = {}
    for label, forward_seconds in FORWARD_PERIOD_SECONDS.items():
        if forward_seconds < period_seconds:
            continue
        if forward_seconds % period_seconds != 0:
            continue
        offsets[label] = forward_seconds // period_seconds
    return offsets
