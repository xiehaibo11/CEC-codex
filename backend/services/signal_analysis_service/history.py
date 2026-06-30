"""
Metric history fetchers for Signal Analysis.

Provides per-metric historical value extraction used by SignalAnalysisService.
"""


class MetricHistoryMixin:
    """Mixin providing per-metric historical value fetchers."""

    def _get_oi_delta_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get OI delta percentage history."""
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
            return [], None, None

        # Bucket by period
        buckets = {}
        for ts, oi in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = float(oi) if oi else None

        # Calculate deltas
        sorted_times = sorted(buckets.keys())
        values = []
        for i in range(1, len(sorted_times)):
            prev_oi = buckets[sorted_times[i-1]]
            curr_oi = buckets[sorted_times[i]]
            if prev_oi and curr_oi and prev_oi != 0:
                delta_pct = ((curr_oi - prev_oi) / prev_oi) * 100
                values.append(delta_pct)

        min_ts = sorted_times[0] if sorted_times else None
        max_ts = sorted_times[-1] if sorted_times else None
        return values, min_ts, max_ts

    def _get_cvd_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get CVD history."""
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
            return [], None, None

        buckets = {}
        for ts, buy, sell in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)

        sorted_times = sorted(buckets.keys())
        values = [buckets[ts]["buy"] - buckets[ts]["sell"] for ts in sorted_times]

        min_ts = sorted_times[0] if sorted_times else None
        max_ts = sorted_times[-1] if sorted_times else None
        return values, min_ts, max_ts

    def _get_depth_ratio_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get depth ratio (bid/ask) history."""
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
            return [], None, None

        buckets = {}
        for ts, bid, ask in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = {"bid": float(bid or 0), "ask": float(ask or 0)}

        sorted_times = sorted(buckets.keys())
        values = []
        for ts in sorted_times:
            ask = buckets[ts]["ask"]
            if ask > 0:
                values.append(buckets[ts]["bid"] / ask)

        min_ts = sorted_times[0] if sorted_times else None
        max_ts = sorted_times[-1] if sorted_times else None
        return values, min_ts, max_ts

    def _get_imbalance_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get order imbalance history."""
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
            return [], None, None

        buckets = {}
        for ts, bid, ask in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = {"bid": float(bid or 0), "ask": float(ask or 0)}

        sorted_times = sorted(buckets.keys())
        values = []
        for ts in sorted_times:
            bid, ask = buckets[ts]["bid"], buckets[ts]["ask"]
            total = bid + ask
            if total > 0:
                values.append((bid - ask) / total)

        min_ts = sorted_times[0] if sorted_times else None
        max_ts = sorted_times[-1] if sorted_times else None
        return values, min_ts, max_ts

    def _get_taker_ratio_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get taker buy/sell log ratio history. Uses ln(buy/sell) for symmetry around 0.

        Log transformation makes the ratio symmetric:
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
            return [], None, None

        buckets = {}
        for ts, buy, sell in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)

        sorted_times = sorted(buckets.keys())
        values = []
        for ts in sorted_times:
            buy = buckets[ts]["buy"]
            sell = buckets[ts]["sell"]
            # Log ratio = ln(buy/sell), symmetric around 0
            if buy > 0 and sell > 0:
                values.append(math.log(buy / sell))

        min_ts = sorted_times[0] if sorted_times else None
        max_ts = sorted_times[-1] if sorted_times else None
        return values, min_ts, max_ts

    def _get_funding_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get funding rate change history. Aligned with K-line FUNDING indicator display."""
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
            return [], None, None

        buckets = {}
        for ts, funding in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            buckets[bucket_ts] = float(funding) * 1000000  # Align with K-line display

        sorted_times = sorted(buckets.keys())
        if len(sorted_times) < 2:
            return [], None, None

        # Calculate change values (current - previous) for each period
        change_values = []
        result_times = []
        for i in range(1, len(sorted_times)):
            ts = sorted_times[i]
            if ts >= start_time_ms:  # Only include values in requested range
                change = buckets[ts] - buckets[sorted_times[i - 1]]
                change_values.append(change)
                result_times.append(ts)

        min_ts = result_times[0] if result_times else None
        max_ts = result_times[-1] if result_times else None
        return change_values, min_ts, max_ts

    def _get_oi_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get OI USD change history.

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
            return [], None, None

        # Build raw buckets with OI and price
        raw_buckets = {}
        for ts, oi, price in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            raw_buckets[bucket_ts] = (float(oi), float(price))

        sorted_times = sorted(raw_buckets.keys())
        if len(sorted_times) < 2:
            return [], None, None

        # Calculate USD change for each bucket
        change_values = []
        result_times = []
        for i in range(1, len(sorted_times)):
            ts = sorted_times[i]
            if ts < start_time_ms:
                continue

            curr_oi, curr_price = raw_buckets[ts]
            prev_oi, _ = raw_buckets[sorted_times[i-1]]
            change_usd = (curr_oi - prev_oi) * curr_price
            change_values.append(round(change_usd, 2))
            result_times.append(ts)

        min_ts = result_times[0] if result_times else None
        max_ts = result_times[-1] if result_times else None
        return change_values, min_ts, max_ts

    def _get_price_change_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get price change percentage history."""
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketTradesAggregated

        records = db.query(
            MarketTradesAggregated.timestamp,
            MarketTradesAggregated.high_price
        ).filter(
            MarketTradesAggregated.exchange == exchange,
            MarketTradesAggregated.symbol == symbol.upper(),
            MarketTradesAggregated.timestamp >= start_time_ms,
            MarketTradesAggregated.timestamp <= current_time_ms,
            MarketTradesAggregated.high_price.isnot(None)
        ).order_by(MarketTradesAggregated.timestamp).all()

        if not records:
            return [], None, None

        buckets = {}
        for ts, high_price in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"first": None, "last": None}
            price = float(high_price)
            if buckets[bucket_ts]["first"] is None:
                buckets[bucket_ts]["first"] = price
            buckets[bucket_ts]["last"] = price

        sorted_times = sorted(buckets.keys())
        values = []
        for i in range(1, len(sorted_times)):
            prev_price = buckets[sorted_times[i-1]]["last"]
            curr_price = buckets[sorted_times[i]]["last"]
            if prev_price and prev_price > 0:
                change_pct = ((curr_price - prev_price) / prev_price) * 100
                values.append(change_pct)

        min_ts = sorted_times[0] if sorted_times else None
        max_ts = sorted_times[-1] if sorted_times else None
        return values, min_ts, max_ts

    def _get_volatility_history(self, db, symbol, interval_ms, start_time_ms, current_time_ms, exchange="hyperliquid"):
        """Get price volatility (high-low)/low percentage history."""
        from services.market_flow_indicators import floor_timestamp
        from database.models import MarketTradesAggregated

        records = db.query(
            MarketTradesAggregated.timestamp,
            MarketTradesAggregated.high_price,
            MarketTradesAggregated.low_price
        ).filter(
            MarketTradesAggregated.exchange == exchange,
            MarketTradesAggregated.symbol == symbol.upper(),
            MarketTradesAggregated.timestamp >= start_time_ms,
            MarketTradesAggregated.timestamp <= current_time_ms,
            MarketTradesAggregated.high_price.isnot(None),
            MarketTradesAggregated.low_price.isnot(None)
        ).order_by(MarketTradesAggregated.timestamp).all()

        if not records:
            return [], None, None

        buckets = {}
        for ts, high_price, low_price in records:
            bucket_ts = floor_timestamp(ts, interval_ms)
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"high": None, "low": None}
            h = float(high_price)
            l = float(low_price)
            if buckets[bucket_ts]["high"] is None or h > buckets[bucket_ts]["high"]:
                buckets[bucket_ts]["high"] = h
            if buckets[bucket_ts]["low"] is None or l < buckets[bucket_ts]["low"]:
                buckets[bucket_ts]["low"] = l

        sorted_times = sorted(buckets.keys())
        values = []
        for ts in sorted_times:
            high = buckets[ts]["high"]
            low = buckets[ts]["low"]
            if high and low and low > 0:
                volatility_pct = ((high - low) / low) * 100
                values.append(volatility_pct)

        min_ts = sorted_times[0] if sorted_times else None
        max_ts = sorted_times[-1] if sorted_times else None
        return values, min_ts, max_ts
