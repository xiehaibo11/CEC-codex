#!/usr/bin/env python3
"""
Trade-aggregated market flow indicators.

Indicators derived from MarketTradesAggregated: CVD, Taker buy/sell, price
change, and volatility.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database.models import MarketTradesAggregated

from services.market_flow_indicators.common import floor_timestamp, decimal_to_float

logger = logging.getLogger(__name__)


def _get_cvd_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get CVD (Cumulative Volume Delta) data.

    CVD = Cumulative(Taker Buy Notional - Taker Sell Notional)
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketTradesAggregated.timestamp,
        MarketTradesAggregated.taker_buy_notional,
        MarketTradesAggregated.taker_sell_notional
    ).filter(
        MarketTradesAggregated.symbol == symbol.upper(),
        MarketTradesAggregated.exchange == exchange.lower(),
        MarketTradesAggregated.timestamp >= start_time,
        MarketTradesAggregated.timestamp <= current_time_ms
    ).order_by(MarketTradesAggregated.timestamp).all()

    if not records:
        from datetime import datetime
        logger.warning(
            f"CVD insufficient data: symbol={symbol}, exchange={exchange}, period={period}, "
            f"query_range=[{datetime.utcfromtimestamp(start_time/1000)} - "
            f"{datetime.utcfromtimestamp(current_time_ms/1000)}], records_found=0"
        )
        return None

    # Aggregate by period
    buckets = {}
    for ts, buy_notional, sell_notional in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        if bucket_ts not in buckets:
            buckets[bucket_ts] = {"buy": Decimal("0"), "sell": Decimal("0")}
        buckets[bucket_ts]["buy"] += buy_notional or Decimal("0")
        buckets[bucket_ts]["sell"] += sell_notional or Decimal("0")

    # Calculate CVD for each period
    sorted_times = sorted(buckets.keys())
    period_deltas = []

    for ts in sorted_times:
        bucket = buckets[ts]
        delta = float(bucket["buy"] - bucket["sell"])
        period_deltas.append(delta)

    if not period_deltas:
        from datetime import datetime
        logger.warning(
            f"CVD insufficient data: symbol={symbol}, period={period}, "
            f"records_found={len(records)}, buckets=0"
        )
        return None

    last_5 = period_deltas[-5:] if len(period_deltas) >= 5 else period_deltas
    current_delta = period_deltas[-1]
    cumulative = sum(period_deltas)

    return {
        "current": current_delta,
        "last_5": last_5,
        "cumulative": cumulative,
        "period": period
    }


def _get_taker_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid", include_debug: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Get Taker Buy/Sell Volume data.

    Returns buy volume, sell volume, and buy/sell ratio.
    If include_debug=True (for Binance), includes debug_snapshot for troubleshooting.
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketTradesAggregated.timestamp,
        MarketTradesAggregated.taker_buy_notional,
        MarketTradesAggregated.taker_sell_notional
    ).filter(
        MarketTradesAggregated.symbol == symbol.upper(),
        MarketTradesAggregated.exchange == exchange.lower(),
        MarketTradesAggregated.timestamp >= start_time,
        MarketTradesAggregated.timestamp <= current_time_ms
    ).order_by(MarketTradesAggregated.timestamp).all()

    if not records:
        return None

    # Aggregate by period
    buckets = {}
    for ts, buy_notional, sell_notional in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        if bucket_ts not in buckets:
            buckets[bucket_ts] = {"buy": Decimal("0"), "sell": Decimal("0")}
        buckets[bucket_ts]["buy"] += buy_notional or Decimal("0")
        buckets[bucket_ts]["sell"] += sell_notional or Decimal("0")

    sorted_times = sorted(buckets.keys())
    ratios = []
    volumes = []

    for ts in sorted_times:
        bucket = buckets[ts]
        buy = float(bucket["buy"])
        sell = float(bucket["sell"])
        ratio = buy / sell if sell > 0 else 1.0
        ratios.append(ratio)
        volumes.append(buy + sell)

    if not ratios:
        return None

    # Current period data
    current_bucket = buckets[sorted_times[-1]]
    current_buy = float(current_bucket["buy"])
    current_sell = float(current_bucket["sell"])
    current_ratio = current_buy / current_sell if current_sell > 0 else 1.0

    last_5_ratios = ratios[-5:] if len(ratios) >= 5 else ratios
    last_5_volumes = volumes[-5:] if len(volumes) >= 5 else volumes

    result = {
        "buy": current_buy,
        "sell": current_sell,
        "ratio": current_ratio,
        "ratio_last_5": last_5_ratios,
        "volume_last_5": last_5_volumes,
        "period": period
    }

    # Add debug snapshot for Binance troubleshooting
    if include_debug:
        # Build buckets summary for debug
        buckets_debug = {}
        for ts in sorted_times:
            bucket = buckets[ts]
            buckets_debug[str(ts)] = {
                "buy": float(bucket["buy"]),
                "sell": float(bucket["sell"]),
                "total": float(bucket["buy"] + bucket["sell"])
            }

        result["debug_snapshot"] = {
            "query_params": {
                "current_time_ms": current_time_ms,
                "start_time": start_time,
                "interval_ms": interval_ms,
                "exchange": exchange,
                "symbol": symbol
            },
            "records_count": len(records),
            "records_ts_range": [records[0][0], records[-1][0]] if records else [],
            "buckets_count": len(buckets),
            "buckets": buckets_debug,
            "result_bucket_ts": sorted_times[-1],
            "result": {
                "buy": current_buy,
                "sell": current_sell,
                "total": current_buy + current_sell,
                "ratio": current_ratio
            }
        }

    return result


def _get_price_change_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get Price Change data.

    Calculates price change percentage over the specified time window.
    Uses high_price from market_trades_aggregated (15-second granularity).

    Returns:
        current: Price change percentage (e.g., 0.15 means +0.15%)
        start_price: Price at the start of the window
        end_price: Current price
        last_5: Last 5 period price changes
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketTradesAggregated.timestamp,
        MarketTradesAggregated.high_price
    ).filter(
        MarketTradesAggregated.symbol == symbol.upper(),
        MarketTradesAggregated.exchange == exchange.lower(),
        MarketTradesAggregated.timestamp >= start_time,
        MarketTradesAggregated.timestamp <= current_time_ms,
        MarketTradesAggregated.high_price.isnot(None)
    ).order_by(MarketTradesAggregated.timestamp).all()

    if not records or len(records) < 2:
        return None

    # Aggregate by period bucket
    buckets = {}
    for ts, high_price in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        if bucket_ts not in buckets:
            buckets[bucket_ts] = {"first_price": None, "last_price": None}
        price = decimal_to_float(high_price)
        if buckets[bucket_ts]["first_price"] is None:
            buckets[bucket_ts]["first_price"] = price
        buckets[bucket_ts]["last_price"] = price

    sorted_times = sorted(buckets.keys())
    if len(sorted_times) < 2:
        return None

    # Calculate price change for each period
    price_changes = []
    for i, ts in enumerate(sorted_times):
        if i == 0:
            continue
        prev_ts = sorted_times[i - 1]
        prev_price = buckets[prev_ts]["last_price"]
        curr_price = buckets[ts]["last_price"]
        if prev_price and prev_price > 0:
            change_pct = ((curr_price - prev_price) / prev_price) * 100
            price_changes.append(change_pct)

    if not price_changes:
        return None

    # Current price change: compare current bucket to one period ago
    current_bucket = buckets[sorted_times[-1]]
    prev_bucket = buckets[sorted_times[-2]] if len(sorted_times) >= 2 else None

    if prev_bucket and prev_bucket["last_price"] and prev_bucket["last_price"] > 0:
        current_change = ((current_bucket["last_price"] - prev_bucket["last_price"])
                          / prev_bucket["last_price"]) * 100
    else:
        current_change = price_changes[-1] if price_changes else 0

    last_5 = price_changes[-5:] if len(price_changes) >= 5 else price_changes

    return {
        "current": current_change,
        "start_price": prev_bucket["last_price"] if prev_bucket else None,
        "end_price": current_bucket["last_price"],
        "last_5": last_5,
        "period": period
    }


def _get_volatility_data(
    db: Session, symbol: str, period: str, interval_ms: int, current_time_ms: int,
    exchange: str = "hyperliquid"
) -> Optional[Dict[str, Any]]:
    """
    Get Volatility (Price Range) data.

    Calculates price volatility as (high - low) / low percentage over the time window.
    Uses high_price and low_price from market_trades_aggregated (15-second granularity).

    Returns:
        current: Current period volatility percentage (e.g., 0.25 means 0.25%)
        high: Highest price in the window
        low: Lowest price in the window
        last_5: Last 5 period volatility values
    """
    lookback_ms = interval_ms * 10
    start_time = current_time_ms - lookback_ms

    records = db.query(
        MarketTradesAggregated.timestamp,
        MarketTradesAggregated.high_price,
        MarketTradesAggregated.low_price
    ).filter(
        MarketTradesAggregated.symbol == symbol.upper(),
        MarketTradesAggregated.exchange == exchange.lower(),
        MarketTradesAggregated.timestamp >= start_time,
        MarketTradesAggregated.timestamp <= current_time_ms,
        MarketTradesAggregated.high_price.isnot(None),
        MarketTradesAggregated.low_price.isnot(None)
    ).order_by(MarketTradesAggregated.timestamp).all()

    if not records:
        return None

    # Aggregate by period bucket - track high and low for each bucket
    buckets = {}
    for ts, high_price, low_price in records:
        bucket_ts = floor_timestamp(ts, interval_ms)
        high = decimal_to_float(high_price)
        low = decimal_to_float(low_price)
        if bucket_ts not in buckets:
            buckets[bucket_ts] = {"high": high, "low": low}
        else:
            if high and (buckets[bucket_ts]["high"] is None or high > buckets[bucket_ts]["high"]):
                buckets[bucket_ts]["high"] = high
            if low and (buckets[bucket_ts]["low"] is None or low < buckets[bucket_ts]["low"]):
                buckets[bucket_ts]["low"] = low

    sorted_times = sorted(buckets.keys())
    if not sorted_times:
        return None

    # Calculate volatility for each period
    volatilities = []
    for ts in sorted_times:
        bucket = buckets[ts]
        high = bucket["high"]
        low = bucket["low"]
        if high and low and low > 0:
            volatility_pct = ((high - low) / low) * 100
            volatilities.append(volatility_pct)

    if not volatilities:
        return None

    current_bucket = buckets[sorted_times[-1]]
    current_high = current_bucket["high"]
    current_low = current_bucket["low"]
    current_volatility = ((current_high - current_low) / current_low * 100
                          if current_high and current_low and current_low > 0 else 0)

    last_5 = volatilities[-5:] if len(volatilities) >= 5 else volatilities

    return {
        "current": current_volatility,
        "high": current_high,
        "low": current_low,
        "last_5": last_5,
        "period": period
    }
