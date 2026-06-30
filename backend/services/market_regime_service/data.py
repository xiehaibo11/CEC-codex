"""
Data fetching and price-metric helpers for market regime classification.

Aggregates OHLC data from flow data, fetches K-line data from the DB (with
optional realtime API merge), and computes price-based metrics (ATR/RSI).
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from database.models import CryptoKline, MarketTradesAggregated
from services.technical_indicators import calculate_indicators
from services.market_flow_indicators import TIMEFRAME_MS

logger = logging.getLogger(__name__)


def fetch_ohlc_from_flow(
    db: Session,
    symbol: str,
    period: str,
    limit: int = 15,
    current_time_ms: Optional[int] = None,
    exchange: str = "hyperliquid"
) -> List[Dict[str, Any]]:
    """
    Aggregate OHLC data from 15-second flow data (MarketTradesAggregated).

    This function builds "simulated K-lines" using flow data, with current_time_ms
    as the anchor point. Each K-line covers one period sliding backwards.

    Args:
        db: Database session
        symbol: Trading symbol (e.g., "BTC")
        period: Timeframe ("1m", "5m", "15m", "1h")
        limit: Number of K-lines to generate (default 15 for ATR14/RSI14)
        current_time_ms: Anchor timestamp in milliseconds (defaults to now)
        exchange: Exchange name (e.g., "hyperliquid", "binance")

    Returns:
        List of OHLC dicts in chronological order (oldest first),
        same format as fetch_kline_data()
    """
    if current_time_ms is None:
        current_time_ms = int(datetime.utcnow().timestamp() * 1000)

    period_ms = TIMEFRAME_MS.get(period)
    if not period_ms:
        logger.warning(f"Unsupported period for flow aggregation: {period}")
        return []

    # Calculate query time range: need limit periods of data
    total_time_ms = limit * period_ms
    start_ts = current_time_ms - total_time_ms
    end_ts = current_time_ms

    # Query all 15-second records in the time range
    records = db.query(
        MarketTradesAggregated.timestamp,
        MarketTradesAggregated.vwap,
        MarketTradesAggregated.high_price,
        MarketTradesAggregated.low_price,
        MarketTradesAggregated.taker_buy_notional,
        MarketTradesAggregated.taker_sell_notional
    ).filter(
        MarketTradesAggregated.symbol == symbol.upper(),
        MarketTradesAggregated.exchange == exchange.lower(),
        MarketTradesAggregated.timestamp >= start_ts,
        MarketTradesAggregated.timestamp < end_ts
    ).order_by(MarketTradesAggregated.timestamp).all()

    if not records:
        logger.warning(f"No flow data for {symbol} in range [{start_ts}, {end_ts})")
        return []

    # Group records by period bucket
    buckets = {}  # bucket_start_ts -> list of records
    for rec in records:
        # Calculate which period bucket this record belongs to
        # Bucket is defined by: bucket_start = end_ts - (i+1)*period_ms to end_ts - i*period_ms
        # We use floor division to find the bucket index from the end
        time_from_end = end_ts - rec.timestamp
        bucket_idx = time_from_end // period_ms
        if bucket_idx >= limit:
            continue  # Outside our limit
        bucket_start = end_ts - (bucket_idx + 1) * period_ms
        if bucket_start not in buckets:
            buckets[bucket_start] = []
        buckets[bucket_start].append(rec)

    # Aggregate each bucket into OHLC
    result = []
    for i in range(limit - 1, -1, -1):  # Iterate from oldest to newest
        bucket_start = end_ts - (i + 1) * period_ms
        bucket_records = buckets.get(bucket_start, [])

        if not bucket_records:
            # No data for this period, skip or use placeholder
            continue

        # Sort by timestamp to get first/last
        bucket_records.sort(key=lambda x: x.timestamp)

        # Aggregate OHLC
        first_rec = bucket_records[0]
        last_rec = bucket_records[-1]

        open_price = float(first_rec.vwap) if first_rec.vwap else 0
        close_price = float(last_rec.vwap) if last_rec.vwap else 0
        high_price = max((float(r.high_price) for r in bucket_records if r.high_price), default=0)
        low_price = min((float(r.low_price) for r in bucket_records if r.low_price), default=0)
        volume = sum(
            (float(r.taker_buy_notional or 0) + float(r.taker_sell_notional or 0))
            for r in bucket_records
        )

        result.append({
            "timestamp": bucket_start // 1000,  # Convert to seconds for consistency
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume
        })

    logger.debug(f"Aggregated {len(result)} OHLC bars from flow data for {symbol}/{period}")
    return result


def _fetch_kline_with_realtime(
    db: Session, symbol: str, period: str, limit: int, current_time_ms: Optional[int]
) -> List[Dict[str, Any]]:
    """
    Fetch K-line data with realtime API call for current candle.
    Merges API data with DB history, API data takes priority for overlapping timestamps.

    Args:
        db: Database session
        symbol: Trading symbol
        period: Timeframe (1m, 5m, 15m, etc.)
        limit: Number of candles to fetch
        current_time_ms: Current timestamp in milliseconds
    """
    from services.hyperliquid_market_data import get_kline_data_from_hyperliquid

    # Fetch recent candles from API (including current unfinished candle)
    api_klines = []
    try:
        # Only fetch 5 candles from API to minimize latency
        raw_data = get_kline_data_from_hyperliquid(symbol, period, count=5, persist=False)
        for k in raw_data:
            # API returns timestamp in ms, convert to seconds for consistency
            ts = k.get("timestamp", 0)
            if ts > 1e12:  # If in milliseconds
                ts = ts // 1000
            api_klines.append({
                "timestamp": ts,
                "open": float(k.get("open", 0)),
                "high": float(k.get("high", 0)),
                "low": float(k.get("low", 0)),
                "close": float(k.get("close", 0)),
                "volume": float(k.get("volume", 0))
            })
        logger.debug(f"Fetched {len(api_klines)} candles from API for {symbol}/{period}")
    except Exception as e:
        logger.warning(f"Failed to fetch realtime K-line from API: {e}, falling back to DB only")
        # Fallback to DB-only
        api_klines = []

    # Fetch history from DB (limit-5 to leave room for API data)
    db_limit = max(limit - 5, limit)  # Fetch enough to ensure we have limit candles after merge
    query = db.query(CryptoKline).filter(
        CryptoKline.symbol == symbol,
        CryptoKline.period == period
    )
    if current_time_ms:
        current_time_s = current_time_ms // 1000
        query = query.filter(CryptoKline.timestamp <= current_time_s)

    db_klines = query.order_by(CryptoKline.timestamp.desc()).limit(db_limit).all()

    # Convert DB klines to dict format
    db_data = {}
    for k in db_klines:
        db_data[k.timestamp] = {
            "timestamp": k.timestamp,
            "open": float(k.open_price) if k.open_price else 0,
            "high": float(k.high_price) if k.high_price else 0,
            "low": float(k.low_price) if k.low_price else 0,
            "close": float(k.close_price) if k.close_price else 0,
            "volume": float(k.volume) if k.volume else 0
        }

    # Merge: API data takes priority (more recent)
    for k in api_klines:
        db_data[k["timestamp"]] = k

    # Sort by timestamp and take last 'limit' candles
    sorted_klines = sorted(db_data.values(), key=lambda x: x["timestamp"])
    return sorted_klines[-limit:] if len(sorted_klines) > limit else sorted_klines


def fetch_kline_data(
    db: Session, symbol: str, period: str = "5m", limit: int = 50,
    current_time_ms: Optional[int] = None, use_realtime: bool = False,
    exchange: str = "hyperliquid"
) -> List[Dict[str, Any]]:
    """
    Fetch K-line data for technical indicator calculation.
    Returns list of dicts with timestamp, open, high, low, close, volume.

    Args:
        db: Database session
        symbol: Trading symbol
        period: Timeframe (1m, 5m, 15m, etc.)
        limit: Number of candles to fetch
        current_time_ms: Optional timestamp for historical queries (backtesting)
        use_realtime: If True, use flow data aggregation for real-time regime calculation
        exchange: Exchange name (e.g., "hyperliquid", "binance")
    """
    # If use_realtime, aggregate OHLC from flow data (15-second buckets)
    # This provides real-time regime calculation without K-line close delay
    if use_realtime:
        return fetch_ohlc_from_flow(db, symbol, period, limit, current_time_ms, exchange=exchange)

    # Original DB-only logic for backtesting
    query = db.query(CryptoKline).filter(
        CryptoKline.symbol == symbol,
        CryptoKline.period == period,
        CryptoKline.exchange == exchange.lower()
    )

    if current_time_ms:
        # Convert ms to seconds for comparison with CryptoKline.timestamp (stored in seconds)
        current_time_s = current_time_ms // 1000
        query = query.filter(CryptoKline.timestamp <= current_time_s)

    klines = query.order_by(CryptoKline.timestamp.desc()).limit(limit).all()

    if not klines:
        return []

    # Reverse to chronological order and convert to dict format
    result = []
    for k in reversed(klines):
        result.append({
            "timestamp": k.timestamp,
            "open": float(k.open_price) if k.open_price else 0,
            "high": float(k.high_price) if k.high_price else 0,
            "low": float(k.low_price) if k.low_price else 0,
            "close": float(k.close_price) if k.close_price else 0,
            "volume": float(k.volume) if k.volume else 0
        })
    return result


def calculate_price_metrics(kline_data: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate price-based metrics using technical indicators.
    Returns: price_atr, price_range_atr, rsi
    """
    if len(kline_data) < 15:  # Need at least 15 bars for ATR14 and RSI14
        return {"price_atr": 0.0, "price_range_atr": 0.0, "rsi": 50.0}

    # Calculate ATR and RSI using technical_indicators service
    indicators = calculate_indicators(kline_data, ["ATR14", "RSI14"])

    atr_values = indicators.get("ATR14", [])
    rsi_values = indicators.get("RSI14", [])

    # Get latest values
    atr = atr_values[-1] if atr_values else 0.0
    rsi = rsi_values[-1] if rsi_values else 50.0

    # Calculate price_atr: (close - open) / ATR (normalized price change)
    if atr > 0 and len(kline_data) >= 1:
        latest = kline_data[-1]
        price_change = latest["close"] - latest["open"]
        price_atr = price_change / atr
        # Calculate price_range_atr: (high - low) / ATR
        price_range = latest["high"] - latest["low"]
        price_range_atr = price_range / atr
    else:
        price_atr = 0.0
        price_range_atr = 0.0

    return {
        "price_atr": price_atr,
        "price_range_atr": price_range_atr,
        "rsi": rsi
    }
