"""Rolling-window bucket value computation per metric."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class BucketComputeMixin:
    """Rolling-window bucket value computation per metric."""

    def _compute_all_bucket_values(
        self, db: Session, symbol: str, metric: str, interval_ms: int, exchange: str = "hyperliquid"
    ) -> Dict[int, float]:
        """
        Compute indicator values for all buckets using the same logic as
        signal_analysis_service. This ensures consistency between statistical
        analysis and backtest preview.

        Returns a dict mapping bucket_timestamp -> indicator_value
        """
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketAssetMetrics, MarketTradesAggregated
        from database.models import MarketOrderbookSnapshots
        from datetime import datetime

        # Query 7 days of data (same as signal_analysis_service)
        current_time_ms = int(datetime.utcnow().timestamp() * 1000)
        start_time_ms = current_time_ms - (7 * 24 * 60 * 60 * 1000)

        if metric == "oi_delta":
            return self._compute_oi_delta_buckets(
                db, symbol, interval_ms, start_time_ms, current_time_ms, exchange
            )
        elif metric == "cvd":
            return self._compute_cvd_buckets(
                db, symbol, interval_ms, start_time_ms, current_time_ms, exchange
            )
        elif metric == "depth_ratio":
            return self._compute_depth_ratio_buckets(
                db, symbol, interval_ms, start_time_ms, current_time_ms, exchange
            )
        elif metric == "order_imbalance":
            return self._compute_imbalance_buckets(
                db, symbol, interval_ms, start_time_ms, current_time_ms, exchange
            )
        elif metric == "taker_ratio":
            return self._compute_taker_ratio_buckets(
                db, symbol, interval_ms, start_time_ms, current_time_ms, exchange
            )
        elif metric == "funding":
            return self._compute_funding_buckets(
                db, symbol, interval_ms, start_time_ms, current_time_ms, exchange
            )
        elif metric == "oi":
            return self._compute_oi_buckets(
                db, symbol, interval_ms, start_time_ms, current_time_ms, exchange
            )
        else:
            logger.warning(f"Unknown metric for bucket computation: {metric}")
            return {}

    def _compute_oi_delta_buckets(
        self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"
    ) -> Dict[int, float]:
        """Compute OI delta percentage for each bucket (same as signal_analysis)."""
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketAssetMetrics

        records = db.query(
            MarketAssetMetrics.timestamp,
            MarketAssetMetrics.open_interest
        ).filter(
            MarketAssetMetrics.exchange == exchange,
            MarketAssetMetrics.symbol == symbol.upper(),
            MarketAssetMetrics.timestamp >= start_time_ms,
            MarketAssetMetrics.timestamp <= current_time_ms
        ).order_by(MarketAssetMetrics.timestamp).all()

        if not records:
            return {}

        # Bucket by period
        buckets = {}
        for ts, oi in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = float(oi) if oi else None

        # Calculate deltas - map each bucket to its delta value
        sorted_times = sorted(buckets.keys())
        result = {}
        for i in range(1, len(sorted_times)):
            prev_oi = buckets[sorted_times[i-1]]
            curr_oi = buckets[sorted_times[i]]
            if prev_oi and curr_oi and prev_oi != 0:
                delta_pct = ((curr_oi - prev_oi) / prev_oi) * 100
                # The delta is associated with the CURRENT bucket
                result[sorted_times[i]] = delta_pct

        return result

    def _compute_cvd_buckets(
        self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"
    ) -> Dict[int, float]:
        """Compute CVD for each bucket."""
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketTradesAggregated

        records = db.query(
            MarketTradesAggregated.timestamp,
            MarketTradesAggregated.taker_buy_notional,
            MarketTradesAggregated.taker_sell_notional
        ).filter(
            MarketTradesAggregated.exchange == exchange,
            MarketTradesAggregated.symbol == symbol.upper(),
            MarketTradesAggregated.timestamp >= start_time_ms,
            MarketTradesAggregated.timestamp <= current_time_ms
        ).order_by(MarketTradesAggregated.timestamp).all()

        if not records:
            return {}

        buckets = {}
        for ts, buy, sell in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)

        result = {}
        for ts in buckets:
            result[ts] = buckets[ts]["buy"] - buckets[ts]["sell"]

        return result

    def _compute_depth_ratio_buckets(
        self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"
    ) -> Dict[int, float]:
        """Compute depth ratio (bid/ask) for each bucket."""
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketOrderbookSnapshots

        records = db.query(
            MarketOrderbookSnapshots.timestamp,
            MarketOrderbookSnapshots.bid_depth_5,
            MarketOrderbookSnapshots.ask_depth_5
        ).filter(
            MarketOrderbookSnapshots.exchange == exchange,
            MarketOrderbookSnapshots.symbol == symbol.upper(),
            MarketOrderbookSnapshots.timestamp >= start_time_ms,
            MarketOrderbookSnapshots.timestamp <= current_time_ms
        ).order_by(MarketOrderbookSnapshots.timestamp).all()

        if not records:
            return {}

        buckets = {}
        for ts, bid, ask in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = {"bid": float(bid or 0), "ask": float(ask or 0)}

        result = {}
        for ts in buckets:
            ask = buckets[ts]["ask"]
            if ask > 0:
                result[ts] = buckets[ts]["bid"] / ask

        return result

    def _compute_imbalance_buckets(
        self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"
    ) -> Dict[int, float]:
        """Compute order imbalance for each bucket."""
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketOrderbookSnapshots

        records = db.query(
            MarketOrderbookSnapshots.timestamp,
            MarketOrderbookSnapshots.bid_depth_5,
            MarketOrderbookSnapshots.ask_depth_5
        ).filter(
            MarketOrderbookSnapshots.exchange == exchange,
            MarketOrderbookSnapshots.symbol == symbol.upper(),
            MarketOrderbookSnapshots.timestamp >= start_time_ms,
            MarketOrderbookSnapshots.timestamp <= current_time_ms
        ).order_by(MarketOrderbookSnapshots.timestamp).all()

        if not records:
            return {}

        buckets = {}
        for ts, bid, ask in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = {"bid": float(bid or 0), "ask": float(ask or 0)}

        result = {}
        for ts in buckets:
            bid, ask = buckets[ts]["bid"], buckets[ts]["ask"]
            total = bid + ask
            if total > 0:
                result[ts] = (bid - ask) / total

        return result

    def _compute_taker_ratio_buckets(
        self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"
    ) -> Dict[int, float]:
        """Compute taker buy/sell log ratio for each bucket.

        Uses ln(buy/sell) for symmetric ratio around 0:
        - ln(2.0) = +0.69 (buyers 2x sellers)
        - ln(1.0) = 0 (balanced)
        - ln(0.5) = -0.69 (sellers 2x buyers)
        """
        import math
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketTradesAggregated

        records = db.query(
            MarketTradesAggregated.timestamp,
            MarketTradesAggregated.taker_buy_notional,
            MarketTradesAggregated.taker_sell_notional
        ).filter(
            MarketTradesAggregated.exchange == exchange,
            MarketTradesAggregated.symbol == symbol.upper(),
            MarketTradesAggregated.timestamp >= start_time_ms,
            MarketTradesAggregated.timestamp <= current_time_ms
        ).order_by(MarketTradesAggregated.timestamp).all()

        if not records:
            return {}

        buckets = {}
        for ts, buy, sell in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)

        result = {}
        for ts in buckets:
            buy = buckets[ts]["buy"]
            sell = buckets[ts]["sell"]
            if buy > 0 and sell > 0:
                result[ts] = math.log(buy / sell)  # Log transformation

        return result

    def _compute_funding_buckets(
        self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"
    ) -> Dict[int, float]:
        """Compute funding rate change for each bucket. Aligned with K-line display."""
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketAssetMetrics

        # Load data for requested range + one extra interval for first change calc
        query_start_ms = start_time_ms - interval_ms

        records = db.query(
            MarketAssetMetrics.timestamp,
            MarketAssetMetrics.funding_rate
        ).filter(
            MarketAssetMetrics.exchange == exchange,
            MarketAssetMetrics.symbol == symbol.upper(),
            MarketAssetMetrics.timestamp >= query_start_ms,
            MarketAssetMetrics.timestamp <= current_time_ms,
            MarketAssetMetrics.funding_rate.isnot(None)
        ).order_by(MarketAssetMetrics.timestamp).all()

        if not records:
            return {}

        # First pass: aggregate raw values by bucket (aligned with K-line display)
        raw_buckets = {}
        for ts, funding in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            raw_buckets[bucket_ts] = float(funding) * 1000000  # Align with K-line display

        sorted_times = sorted(raw_buckets.keys())
        if len(sorted_times) < 2:
            return {}

        # Second pass: compute change values
        result = {}
        for i in range(1, len(sorted_times)):
            ts = sorted_times[i]
            if ts >= start_time_ms:  # Only include values in requested range
                change = raw_buckets[ts] - raw_buckets[sorted_times[i - 1]]
                result[ts] = change

        return result

    def _compute_oi_buckets(
        self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"
    ) -> Dict[int, float]:
        """Compute OI USD change for each bucket.

        OI change = (current_OI - previous_OI) × mark_price
        Returns USD value (can be positive or negative).
        """
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketAssetMetrics

        # Load data for requested range + one extra interval for first change calc
        query_start_ms = start_time_ms - interval_ms

        records = db.query(
            MarketAssetMetrics.timestamp,
            MarketAssetMetrics.open_interest,
            MarketAssetMetrics.mark_price
        ).filter(
            MarketAssetMetrics.exchange == exchange,
            MarketAssetMetrics.symbol == symbol.upper(),
            MarketAssetMetrics.timestamp >= query_start_ms,
            MarketAssetMetrics.timestamp <= current_time_ms,
            MarketAssetMetrics.open_interest.isnot(None),
            MarketAssetMetrics.mark_price.isnot(None)
        ).order_by(MarketAssetMetrics.timestamp).all()

        if not records:
            return {}

        # Build raw buckets with OI and price
        raw_buckets = {}
        for ts, oi, price in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            raw_buckets[bucket_ts] = (float(oi), float(price))

        sorted_times = sorted(raw_buckets.keys())
        if len(sorted_times) < 2:
            return {}

        # Calculate USD change for each bucket
        change_buckets = {}
        for i in range(1, len(sorted_times)):
            ts = sorted_times[i]
            if ts < start_time_ms:
                continue

            curr_oi, curr_price = raw_buckets[ts]
            prev_oi, _ = raw_buckets[sorted_times[i-1]]
            change_usd = (curr_oi - prev_oi) * curr_price
            change_buckets[ts] = round(change_usd, 2)

        return change_buckets

    def _compute_taker_volume_buckets(
        self, db, symbol, interval_ms
    ) -> Dict[int, Dict]:
        """Compute taker volume data (log_ratio and volume) for each bucket.

        Uses ln(buy/sell) for symmetric ratio around 0.
        """
        import math
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketTradesAggregated
        from datetime import datetime

        current_time_ms = int(datetime.utcnow().timestamp() * 1000)
        start_time_ms = current_time_ms - (7 * 24 * 60 * 60 * 1000)

        records = db.query(
            MarketTradesAggregated.timestamp,
            MarketTradesAggregated.taker_buy_notional,
            MarketTradesAggregated.taker_sell_notional
        ).filter(
            MarketTradesAggregated.symbol == symbol.upper(),
            MarketTradesAggregated.timestamp >= start_time_ms,
            MarketTradesAggregated.timestamp <= current_time_ms
        ).order_by(MarketTradesAggregated.timestamp).all()

        if not records:
            return {}

        buckets = {}
        for ts, buy, sell in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)

        # Calculate log ratio and volume for each bucket
        result = {}
        for ts, data in buckets.items():
            buy, sell = data["buy"], data["sell"]
            total = buy + sell
            if buy > 0 and sell > 0 and total > 0:
                result[ts] = {
                    "log_ratio": math.log(buy / sell),
                    "ratio": buy / sell,  # Original ratio for display
                    "volume": total
                }

        return result

