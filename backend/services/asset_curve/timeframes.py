"""Timeframe and date parsing helpers for asset curve queries."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional

DEFAULT_TIMEFRAME = "5m"
LIVE_ENVIRONMENTS = {"testnet", "mainnet"}
HYPERLIQUID_TRADING_MODES = {"hyperliquid", "testnet", "mainnet"}

# Bucket sizes in minutes for each timeframe option.
TIMEFRAME_BUCKET_MINUTES: Dict[str, int] = {
    "5m": 5,
    "1h": 60,
    "1d": 60 * 24,
}


def get_bucket_minutes(timeframe: str) -> int:
    return TIMEFRAME_BUCKET_MINUTES.get(
        timeframe,
        TIMEFRAME_BUCKET_MINUTES[DEFAULT_TIMEFRAME],
    )


def get_bucket_seconds(bucket_minutes: int) -> int:
    bucket_seconds = bucket_minutes * 60
    if bucket_seconds <= 0:
        return TIMEFRAME_BUCKET_MINUTES[DEFAULT_TIMEFRAME] * 60
    return bucket_seconds


def resolve_effective_environment(
    trading_mode: str,
    environment: Optional[str],
) -> Optional[str]:
    if environment not in LIVE_ENVIRONMENTS and trading_mode in LIVE_ENVIRONMENTS:
        return trading_mode
    return environment


def get_environment_filter(environment: Optional[str]) -> Optional[str]:
    return environment if environment in LIVE_ENVIRONMENTS else None


def parse_date_filter(
    value: Optional[str],
    field_name: str,
    logger: logging.Logger,
) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        logger.warning(f"Invalid {field_name} format: {value}")
        return None
