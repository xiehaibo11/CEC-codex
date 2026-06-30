"""Raw data loading and point-in-time indicator calculations."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class IndicatorTimeMixin:
    """Raw data loading and point-in-time indicator calculations."""

    def _load_raw_data_for_metric(
        self, db: Session, symbol: str, metric: str,
        kline_min_ts: int, kline_max_ts: int, interval_ms: int,
        exchange: str = "hyperliquid"
    ) -> List[tuple]:
        """
        Load raw 15-second granularity data for a metric.
        Returns list of (timestamp, value1, value2, ...) tuples.
        """
        from database.models import MarketTradesAggregated, MarketAssetMetrics, MarketOrderbookSnapshots

        logger.warning(f"[Backtest] _load_raw_data_for_metric: symbol={symbol}, metric={metric}, "
                       f"exchange={exchange}, ts_range=[{kline_min_ts}, {kline_max_ts}], interval_ms={interval_ms}")

        # Extend range to include lookback period for first check point
        lookback_ms = interval_ms * 10
        start_time = (kline_min_ts - lookback_ms) if kline_min_ts else None

        result = []
        table_name = "unknown"

        if metric in ("cvd", "taker_ratio"):
            table_name = "market_trades_aggregated"
            query = db.query(
                MarketTradesAggregated.timestamp,
                MarketTradesAggregated.taker_buy_notional,
                MarketTradesAggregated.taker_sell_notional
            ).filter(
                MarketTradesAggregated.exchange == exchange,
                MarketTradesAggregated.symbol == symbol.upper()
            )
            if start_time:
                query = query.filter(MarketTradesAggregated.timestamp >= start_time)
            if kline_max_ts:
                query = query.filter(MarketTradesAggregated.timestamp <= kline_max_ts)
            result = query.order_by(MarketTradesAggregated.timestamp).all()

        elif metric in ("oi_delta", "oi"):
            table_name = "market_asset_metrics"
            query = db.query(
                MarketAssetMetrics.timestamp,
                MarketAssetMetrics.open_interest
            ).filter(
                MarketAssetMetrics.exchange == exchange,
                MarketAssetMetrics.symbol == symbol.upper()
            )
            if start_time:
                query = query.filter(MarketAssetMetrics.timestamp >= start_time)
            if kline_max_ts:
                query = query.filter(MarketAssetMetrics.timestamp <= kline_max_ts)
            result = query.order_by(MarketAssetMetrics.timestamp).all()

        elif metric in ("order_imbalance", "depth_ratio"):
            table_name = "market_orderbook_snapshots"
            query = db.query(
                MarketOrderbookSnapshots.timestamp,
                MarketOrderbookSnapshots.bid_depth_5,
                MarketOrderbookSnapshots.ask_depth_5
            ).filter(
                MarketOrderbookSnapshots.exchange == exchange,
                MarketOrderbookSnapshots.symbol == symbol.upper()
            )
            if start_time:
                query = query.filter(MarketOrderbookSnapshots.timestamp >= start_time)
            if kline_max_ts:
                query = query.filter(MarketOrderbookSnapshots.timestamp <= kline_max_ts)
            result = query.order_by(MarketOrderbookSnapshots.timestamp).all()

        elif metric in ("price_change", "volatility"):
            table_name = "market_trades_aggregated"
            query = db.query(
                MarketTradesAggregated.timestamp,
                MarketTradesAggregated.high_price,
                MarketTradesAggregated.low_price
            ).filter(
                MarketTradesAggregated.exchange == exchange,
                MarketTradesAggregated.symbol == symbol.upper()
            )
            if start_time:
                query = query.filter(MarketTradesAggregated.timestamp >= start_time)
            if kline_max_ts:
                query = query.filter(MarketTradesAggregated.timestamp <= kline_max_ts)
            result = query.order_by(MarketTradesAggregated.timestamp).all()

        elif metric == "funding":
            table_name = "market_asset_metrics"
            query = db.query(
                MarketAssetMetrics.timestamp,
                MarketAssetMetrics.funding_rate
            ).filter(
                MarketAssetMetrics.exchange == exchange,
                MarketAssetMetrics.symbol == symbol.upper(),
                MarketAssetMetrics.funding_rate.isnot(None)
            )
            if start_time:
                query = query.filter(MarketAssetMetrics.timestamp >= start_time)
            if kline_max_ts:
                query = query.filter(MarketAssetMetrics.timestamp <= kline_max_ts)
            result = query.order_by(MarketAssetMetrics.timestamp).all()

        else:
            logger.warning(f"[Backtest] UNKNOWN metric: {metric}, returning empty data")
            return []

        if len(result) == 0:
            logger.warning(f"[Backtest] NO DATA in {table_name} for symbol={symbol.upper()}, "
                           f"metric={metric}, ts_range=[{start_time}, {kline_max_ts}]")
        else:
            logger.warning(f"[Backtest] Loaded {len(result)} rows from {table_name} for {symbol}/{metric}")

        return result

    def _generate_check_points(
        self, raw_data: List[tuple], kline_min_ts: int, kline_max_ts: int, check_interval_ms: int
    ) -> List[int]:
        """Generate check points every 15 seconds within the time range."""
        if not raw_data:
            return []

        # Use actual data timestamps as check points (they are already 15s aligned)
        timestamps = [r[0] for r in raw_data]

        # Filter to requested range
        if kline_min_ts:
            timestamps = [ts for ts in timestamps if ts >= kline_min_ts]
        if kline_max_ts:
            timestamps = [ts for ts in timestamps if ts <= kline_max_ts]

        return sorted(set(timestamps))

    def _calculate_indicator_at_time(
        self, raw_data: List[tuple], metric: str, check_time: int, interval_ms: int,
        timestamps_index: List[int] = None
    ) -> Optional[float]:
        """
        Calculate indicator value at a specific check time.
        Simulates real-time detection: only uses data up to check_time.

        Performance optimization: uses binary search instead of linear filtering.
        If timestamps_index is provided, uses it for O(log n) lookup.
        """
        import bisect

        # Same lookback as real-time detection
        lookback_ms = interval_ms * 10
        start_time = check_time - lookback_ms

        # Use binary search for O(log n) instead of O(n) linear filter
        if timestamps_index is not None:
            # Binary search for range [start_time, check_time]
            left_idx = bisect.bisect_left(timestamps_index, start_time)
            right_idx = bisect.bisect_right(timestamps_index, check_time)
            relevant_data = raw_data[left_idx:right_idx]
        else:
            # Fallback to linear filter for backward compatibility
            relevant_data = [r for r in raw_data if start_time <= r[0] <= check_time]

        if not relevant_data:
            return None

        if metric == "cvd":
            return self._calc_cvd_at_time(relevant_data, interval_ms)
        elif metric == "oi_delta":
            return self._calc_oi_delta_at_time(relevant_data, interval_ms)
        elif metric == "order_imbalance":
            return self._calc_imbalance_at_time(relevant_data, interval_ms)
        elif metric == "depth_ratio":
            return self._calc_depth_ratio_at_time(relevant_data, interval_ms)
        elif metric == "taker_ratio":
            return self._calc_taker_ratio_at_time(relevant_data, interval_ms)
        elif metric == "price_change":
            return self._calc_price_change_at_time(relevant_data, interval_ms)
        elif metric == "volatility":
            return self._calc_volatility_at_time(relevant_data, interval_ms)
        elif metric == "oi":
            return self._calc_oi_at_time(relevant_data, interval_ms)
        elif metric == "funding":
            return self._calc_funding_at_time(relevant_data, interval_ms)
        return None

    def _calc_cvd_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate CVD at a specific time (same logic as _get_cvd_data)."""
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, buy, sell in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)

        if not buckets:
            return None

        # Return last bucket's delta (same as real-time detection)
        sorted_times = sorted(buckets.keys())
        last_bucket = buckets[sorted_times[-1]]
        return last_bucket["buy"] - last_bucket["sell"]

    def _calc_oi_delta_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate OI delta percentage at a specific time."""
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, oi in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = float(oi) if oi else None

        sorted_times = sorted(buckets.keys())
        if len(sorted_times) < 2:
            return None

        prev_oi = buckets[sorted_times[-2]]
        curr_oi = buckets[sorted_times[-1]]
        if prev_oi and curr_oi and prev_oi != 0:
            return ((curr_oi - prev_oi) / prev_oi) * 100
        return None

    def _calc_oi_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate absolute OI value at a specific time."""
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, oi in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = float(oi) if oi else None

        if not buckets:
            return None

        sorted_times = sorted(buckets.keys())
        return buckets[sorted_times[-1]]

    def _calc_funding_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """
        Calculate funding rate change at a specific time.
        Aligned with K-line display: raw × 1000000.
        Returns change between current and previous bucket.
        """
        from services.market_flow_indicators import floor_timestamp

        # Aggregate by bucket, keep last value per bucket
        buckets = {}
        for ts, funding in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if funding is not None:
                buckets[bucket_ts] = float(funding) * 1000000  # Align with K-line display

        if len(buckets) < 2:
            return None

        sorted_times = sorted(buckets.keys())
        # Return change: current - previous
        curr = buckets[sorted_times[-1]]
        prev = buckets[sorted_times[-2]]
        return curr - prev

    def _calc_imbalance_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate order book imbalance at a specific time."""
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, bid, ask in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = {"bid": float(bid or 0), "ask": float(ask or 0)}

        if not buckets:
            return None

        sorted_times = sorted(buckets.keys())
        last = buckets[sorted_times[-1]]
        total = last["bid"] + last["ask"]
        if total > 0:
            return (last["bid"] - last["ask"]) / total
        return None

    def _calc_depth_ratio_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate depth ratio (bid/ask) at a specific time."""
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, bid, ask in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = {"bid": float(bid or 0), "ask": float(ask or 0)}

        if not buckets:
            return None

        sorted_times = sorted(buckets.keys())
        last = buckets[sorted_times[-1]]
        if last["ask"] > 0:
            return last["bid"] / last["ask"]
        return None

    def _calc_taker_ratio_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate taker buy/sell ratio at a specific time.

        Uses direct ratio (buy/sell) to match real-time detection in market_flow_indicators.py.
        """
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, buy, sell in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)

        if not buckets:
            return None

        sorted_times = sorted(buckets.keys())
        last = buckets[sorted_times[-1]]
        if last["sell"] > 0:
            return last["buy"] / last["sell"]
        return 1.0

    def _calc_price_change_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate price change percentage at a specific time.

        Data format: (timestamp, high_price, low_price)
        Returns percentage change from previous period to current period.
        """
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, high, low in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            price = float(high) if high else None
            if price:
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = {"first": price, "last": price}
                else:
                    buckets[bucket_ts]["last"] = price

        sorted_times = sorted(buckets.keys())
        if len(sorted_times) < 2:
            return None

        prev_price = buckets[sorted_times[-2]]["last"]
        curr_price = buckets[sorted_times[-1]]["last"]
        if prev_price and prev_price > 0:
            return ((curr_price - prev_price) / prev_price) * 100
        return None

    def _calc_volatility_at_time(self, data: List[tuple], interval_ms: int) -> Optional[float]:
        """Calculate volatility (price range) percentage at a specific time.

        Data format: (timestamp, high_price, low_price)
        Returns (high - low) / low * 100 for the current period.
        """
        from services.market_flow_indicators import floor_timestamp

        buckets = {}
        for ts, high, low in data:
            bucket_ts = floor_timestamp(ts, interval_ms)
            h = float(high) if high else None
            l = float(low) if low else None
            if h and l:
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = {"high": h, "low": l}
                else:
                    if h > buckets[bucket_ts]["high"]:
                        buckets[bucket_ts]["high"] = h
                    if l < buckets[bucket_ts]["low"]:
                        buckets[bucket_ts]["low"] = l

        if not buckets:
            return None

        sorted_times = sorted(buckets.keys())
        last = buckets[sorted_times[-1]]
        if last["low"] > 0:
            return ((last["high"] - last["low"]) / last["low"]) * 100
        return None

