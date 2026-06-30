#!/usr/bin/env python3
"""
Asset-metric market flow indicators.

Indicators derived from MarketAssetMetrics: Open Interest USD change, Open
Interest delta percentage, and funding rate.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database.models import MarketAssetMetrics

from services.market_flow_indicators.common import (
    floor_timestamp,
    decimal_to_float,
    _log_insufficient_data_once,
)

logger = logging.getLogger(__name__)


def _get_oi_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get Open Interest USD change data.

    OI change measures the absolute USD value change in open interest over the period.
    Formula: (current_OI - previous_OI) × mark_price
    Returns current change and last 5 change values (in USD, can be positive or negative).
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketAssetMetrics.timestamp,
        MarketAssetMetrics.open_interest,
        MarketAssetMetrics.mark_price
    ).filter(
        MarketAssetMetrics.symbol == symbol.upper(),
        MarketAssetMetrics.exchange == exchange.lower(),
        MarketAssetMetrics.timestamp >= start_time,
        MarketAssetMetrics.timestamp <= current_time_ms
    ).order_by(MarketAssetMetrics.timestamp).all()

    if not records:
        logger.warning(f"OI insufficient data: symbol={symbol}, period={period}, records_found=0")
        return None

    # Aggregate by period - take last value in each bucket
    buckets = {}
    for ts, oi, price in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        buckets[bucket_ts] = (oi, price)

    sorted_times = sorted(buckets.keys())
    if len(sorted_times) < 2:
        logger.warning(f"OI insufficient data: symbol={symbol}, buckets={len(sorted_times)}, need_min=2")
        return None

    # Calculate OI USD changes: (current_OI - previous_OI) × mark_price
    oi_changes = []
    for i in range(1, len(sorted_times)):
        curr_oi, curr_price = buckets[sorted_times[i]]
        prev_oi, _ = buckets[sorted_times[i-1]]
        if curr_oi and prev_oi and curr_price:
            curr_oi_f = decimal_to_float(curr_oi)
            prev_oi_f = decimal_to_float(prev_oi)
            price_f = decimal_to_float(curr_price)
            change_usd = (curr_oi_f - prev_oi_f) * price_f
            oi_changes.append(round(change_usd, 2))

    if not oi_changes:
        _log_insufficient_data_once(
            f"oi:{exchange.lower()}:{symbol.upper()}:{period}:valid_changes",
            f"OI insufficient data: symbol={symbol}, valid_changes=0",
        )
        return None

    return {
        "current": oi_changes[-1],
        "last_5": oi_changes[-5:] if len(oi_changes) >= 5 else oi_changes,
        "period": period
    }


def _get_oi_delta_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get Open Interest Delta (change percentage) data.

    Returns current OI change % and last 5 changes.
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketAssetMetrics.timestamp,
        MarketAssetMetrics.open_interest
    ).filter(
        MarketAssetMetrics.symbol == symbol.upper(),
        MarketAssetMetrics.exchange == exchange.lower(),
        MarketAssetMetrics.timestamp >= start_time,
        MarketAssetMetrics.timestamp <= current_time_ms
    ).order_by(MarketAssetMetrics.timestamp).all()

    if not records:
        from datetime import datetime
        _log_insufficient_data_once(
            f"oi_delta:{exchange.lower()}:{symbol.upper()}:{period}:records",
            f"OI_DELTA insufficient data: symbol={symbol}, period={period}, "
            f"query_range=[{datetime.utcfromtimestamp(start_time/1000)} - "
            f"{datetime.utcfromtimestamp(current_time_ms/1000)}], records_found=0"
        )
        return None

    # Aggregate by period - take last value in each bucket
    buckets = {}
    for ts, oi in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        buckets[bucket_ts] = oi

    sorted_times = sorted(buckets.keys())
    if len(sorted_times) < 2:
        _log_insufficient_data_once(
            f"oi_delta:{exchange.lower()}:{symbol.upper()}:{period}:buckets",
            f"OI_DELTA insufficient data: symbol={symbol}, period={period}, "
            f"records_found={len(records)}, buckets={len(sorted_times)}, need_min=2"
        )
        return None

    # Calculate OI changes
    oi_values = [decimal_to_float(buckets[ts]) for ts in sorted_times]
    oi_changes = []
    for i in range(1, len(oi_values)):
        if oi_values[i] and oi_values[i-1] and oi_values[i-1] != 0:
            change_pct = ((oi_values[i] - oi_values[i-1]) / oi_values[i-1]) * 100
            oi_changes.append(change_pct)

    if not oi_changes:
        _log_insufficient_data_once(
            f"oi_delta:{exchange.lower()}:{symbol.upper()}:{period}:valid_changes",
            f"OI_DELTA insufficient data: symbol={symbol}, period={period}, "
            f"records_found={len(records)}, buckets={len(sorted_times)}, valid_changes=0"
        )
        return None

    current_change = oi_changes[-1]
    last_5 = oi_changes[-5:] if len(oi_changes) >= 5 else oi_changes

    return {
        "current": current_change,
        "last_5": last_5,
        "period": period
    }


def _get_funding_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get Funding Rate data.

    Returns current funding rate and last 5 values.
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketAssetMetrics.timestamp,
        MarketAssetMetrics.funding_rate
    ).filter(
        MarketAssetMetrics.symbol == symbol.upper(),
        MarketAssetMetrics.exchange == exchange.lower(),
        MarketAssetMetrics.timestamp >= start_time,
        MarketAssetMetrics.timestamp <= current_time_ms,
        MarketAssetMetrics.funding_rate.isnot(None)
    ).order_by(MarketAssetMetrics.timestamp).all()

    if not records:
        return None

    # Aggregate by period - take last value in each bucket
    buckets = {}
    for ts, funding in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        buckets[bucket_ts] = funding

    sorted_times = sorted(buckets.keys())
    if not sorted_times:
        return None

    # Get funding rate values aligned with K-line chart display
    # Database stores decimal form (e.g., 0.0000125)
    # K-line chart: raw × 100 (to %) × 10000 = raw × 1000000 for display
    # This gives values like 12.5 when raw is 0.0000125
    funding_values = []
    for ts in sorted_times:
        fr = buckets[ts]
        if fr is not None:
            funding_values.append(float(fr) * 1000000)  # Align with K-line display

    if not funding_values:
        return None

    current_val = funding_values[-1]
    # Convert back to percentage for display: val / 10000 = percentage
    current_pct = current_val / 10000

    # Calculate change from previous period
    if len(funding_values) >= 2:
        change_val = current_val - funding_values[-2]
    else:
        change_val = 0.0
    change_pct = change_val / 10000

    last_5 = funding_values[-5:] if len(funding_values) >= 5 else funding_values

    # Calculate annualized rate (assuming 8-hour funding periods, 3 per day)
    annualized = current_pct * 3 * 365

    return {
        "current": current_val,        # Current rate (K-line display unit)
        "current_pct": current_pct,    # Current rate in percentage
        "change": change_val,          # Change from previous period (K-line display unit)
        "change_pct": change_pct,      # Change in percentage
        "last_5": last_5,              # Last 5 values (K-line display unit)
        "annualized": annualized,      # Annualized rate in percentage
        "period": period
    }
