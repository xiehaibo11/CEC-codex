#!/usr/bin/env python3
"""
Order-book market flow indicators.

Indicators derived from MarketOrderbookSnapshots: bid/ask depth ratio and
order-book imbalance.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database.models import MarketOrderbookSnapshots

from services.market_flow_indicators.common import floor_timestamp, decimal_to_float

logger = logging.getLogger(__name__)


def _get_depth_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get Order Book Depth data.

    Returns bid/ask depth ratio and last 5 values.
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketOrderbookSnapshots.timestamp,
        MarketOrderbookSnapshots.bid_depth_5,
        MarketOrderbookSnapshots.ask_depth_5,
        MarketOrderbookSnapshots.spread
    ).filter(
        MarketOrderbookSnapshots.symbol == symbol.upper(),
        MarketOrderbookSnapshots.exchange == exchange.lower(),
        MarketOrderbookSnapshots.timestamp >= start_time,
        MarketOrderbookSnapshots.timestamp <= current_time_ms
    ).order_by(MarketOrderbookSnapshots.timestamp).all()

    if not records:
        return None

    # Aggregate by period - take last value in each bucket
    buckets = {}
    for ts, bid_depth, ask_depth, spread in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        buckets[bucket_ts] = {
            "bid": bid_depth,
            "ask": ask_depth,
            "spread": spread
        }

    sorted_times = sorted(buckets.keys())
    if not sorted_times:
        return None

    # Calculate depth ratios
    ratios = []
    for ts in sorted_times:
        bucket = buckets[ts]
        bid = decimal_to_float(bucket["bid"]) or 0
        ask = decimal_to_float(bucket["ask"]) or 0
        ratio = bid / ask if ask > 0 else 1.0
        ratios.append(ratio)

    current_bucket = buckets[sorted_times[-1]]
    current_bid = decimal_to_float(current_bucket["bid"]) or 0
    current_ask = decimal_to_float(current_bucket["ask"]) or 0
    current_ratio = current_bid / current_ask if current_ask > 0 else 1.0
    current_spread = decimal_to_float(current_bucket["spread"])

    last_5_ratios = ratios[-5:] if len(ratios) >= 5 else ratios

    return {
        "bid": current_bid,
        "ask": current_ask,
        "ratio": current_ratio,
        "ratio_last_5": last_5_ratios,
        "spread": current_spread,
        "period": period
    }


def _get_imbalance_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get Order Book Imbalance data.

    Imbalance = (Bid - Ask) / (Bid + Ask), range -1 to 1
    Positive = more bid support, Negative = more ask pressure
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketOrderbookSnapshots.timestamp,
        MarketOrderbookSnapshots.bid_depth_5,
        MarketOrderbookSnapshots.ask_depth_5
    ).filter(
        MarketOrderbookSnapshots.symbol == symbol.upper(),
        MarketOrderbookSnapshots.exchange == exchange.lower(),
        MarketOrderbookSnapshots.timestamp >= start_time,
        MarketOrderbookSnapshots.timestamp <= current_time_ms
    ).order_by(MarketOrderbookSnapshots.timestamp).all()

    if not records:
        return None

    # Aggregate by period - take last value in each bucket
    buckets = {}
    for ts, bid_depth, ask_depth in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        buckets[bucket_ts] = {"bid": bid_depth, "ask": ask_depth}

    sorted_times = sorted(buckets.keys())
    if not sorted_times:
        return None

    # Calculate imbalance values
    imbalances = []
    for ts in sorted_times:
        bucket = buckets[ts]
        bid = decimal_to_float(bucket["bid"]) or 0
        ask = decimal_to_float(bucket["ask"]) or 0
        total = bid + ask
        imbalance = (bid - ask) / total if total > 0 else 0.0
        imbalances.append(imbalance)

    current_imbalance = imbalances[-1]
    last_5 = imbalances[-5:] if len(imbalances) >= 5 else imbalances

    return {
        "current": current_imbalance,
        "last_5": last_5,
        "period": period
    }
