"""Incremental bucket window maintenance (add/remove/aggregate)."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class BucketWindowMixin:
    """Incremental bucket window maintenance (add/remove/aggregate)."""

    def _add_to_bucket(self, buckets: Dict, bucket_ts: int, row: tuple, metric: str):
        """Add a data point to bucket aggregation."""
        if metric == 'cvd':
            buy, sell = row[1], row[2]
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0, "count": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)
            buckets[bucket_ts]["count"] += 1

        elif metric == 'order_imbalance' or metric == 'depth_ratio':
            bid, ask = row[1], row[2]
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"bid": 0, "ask": 0, "count": 0}
            # Take last value for orderbook data
            buckets[bucket_ts]["bid"] = float(bid or 0)
            buckets[bucket_ts]["ask"] = float(ask or 0)
            buckets[bucket_ts]["count"] += 1

        elif metric == 'funding':
            funding = row[1]
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"value": None, "count": 0}
            # Apply * 1000000 scaling like original
            buckets[bucket_ts]["value"] = float(funding) * 1000000 if funding is not None else None
            buckets[bucket_ts]["count"] += 1

        elif metric == 'oi_delta':
            oi = row[1]
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"value": None, "count": 0}
            buckets[bucket_ts]["value"] = float(oi) if oi else None
            buckets[bucket_ts]["count"] += 1

        elif metric == 'taker_ratio':
            buy, sell = row[1], row[2]
            if bucket_ts not in buckets:
                buckets[bucket_ts] = {"buy": 0, "sell": 0, "count": 0}
            buckets[bucket_ts]["buy"] += float(buy or 0)
            buckets[bucket_ts]["sell"] += float(sell or 0)
            buckets[bucket_ts]["count"] += 1

        elif metric in ('volatility', 'price_change'):
            # Data format: (timestamp, high_price, low_price)
            high, low = row[1], row[2]
            h = float(high) if high else None
            l = float(low) if low else None
            if h and l:
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = {"high": h, "low": l, "count": 0}
                else:
                    # Track max high and min low for the bucket
                    if h > buckets[bucket_ts]["high"]:
                        buckets[bucket_ts]["high"] = h
                    if l < buckets[bucket_ts]["low"]:
                        buckets[bucket_ts]["low"] = l
                buckets[bucket_ts]["count"] += 1

    def _remove_from_bucket(self, buckets: Dict, bucket_ts: int, row: tuple, metric: str):
        """Remove a data point from bucket aggregation (for sliding window)."""
        if bucket_ts not in buckets:
            return

        if metric == 'cvd':
            buy, sell = row[1], row[2]
            buckets[bucket_ts]["buy"] -= float(buy or 0)
            buckets[bucket_ts]["sell"] -= float(sell or 0)
            buckets[bucket_ts]["count"] -= 1
            if buckets[bucket_ts]["count"] <= 0:
                del buckets[bucket_ts]

        elif metric in ('order_imbalance', 'depth_ratio', 'funding', 'oi_delta'):
            buckets[bucket_ts]["count"] -= 1
            if buckets[bucket_ts]["count"] <= 0:
                del buckets[bucket_ts]

        elif metric == 'taker_ratio':
            buy, sell = row[1], row[2]
            buckets[bucket_ts]["buy"] -= float(buy or 0)
            buckets[bucket_ts]["sell"] -= float(sell or 0)
            buckets[bucket_ts]["count"] -= 1
            if buckets[bucket_ts]["count"] <= 0:
                del buckets[bucket_ts]

        elif metric in ('volatility', 'price_change'):
            # For volatility, we just track count - high/low are recalculated
            buckets[bucket_ts]["count"] -= 1
            if buckets[bucket_ts]["count"] <= 0:
                del buckets[bucket_ts]

    def _calc_from_buckets(self, buckets: Dict, metric: str) -> Optional[float]:
        """Calculate indicator value from current bucket state."""
        import math

        # Filter to valid buckets only
        valid_buckets = {k: v for k, v in buckets.items() if v.get("count", 0) > 0}
        if not valid_buckets:
            return None

        sorted_times = sorted(valid_buckets.keys())

        if metric == 'cvd':
            last = valid_buckets[sorted_times[-1]]
            return last["buy"] - last["sell"]

        elif metric == 'order_imbalance':
            last = valid_buckets[sorted_times[-1]]
            total = last["bid"] + last["ask"]
            return (last["bid"] - last["ask"]) / total if total > 0 else None

        elif metric == 'depth_ratio':
            last = valid_buckets[sorted_times[-1]]
            return last["bid"] / last["ask"] if last["ask"] > 0 else None

        elif metric == 'funding':
            if len(sorted_times) < 2:
                return None
            prev_val = valid_buckets[sorted_times[-2]]["value"]
            curr_val = valid_buckets[sorted_times[-1]]["value"]
            if prev_val is not None and curr_val is not None:
                return curr_val - prev_val
            return None

        elif metric == 'oi_delta':
            if len(sorted_times) < 2:
                return None
            prev_val = valid_buckets[sorted_times[-2]]["value"]
            curr_val = valid_buckets[sorted_times[-1]]["value"]
            if prev_val is not None and curr_val is not None and prev_val != 0:
                return ((curr_val - prev_val) / prev_val) * 100
            return None

        elif metric == 'taker_ratio':
            last = valid_buckets[sorted_times[-1]]
            if last["sell"] > 0:
                return last["buy"] / last["sell"]
            return 1.0

        elif metric == 'volatility':
            last = valid_buckets[sorted_times[-1]]
            if last.get("low", 0) > 0:
                return ((last["high"] - last["low"]) / last["low"]) * 100
            return None

        elif metric == 'price_change':
            if len(sorted_times) < 2:
                return None
            prev = valid_buckets[sorted_times[-2]]
            curr = valid_buckets[sorted_times[-1]]
            # Use midpoint of high/low as price proxy
            prev_price = (prev["high"] + prev["low"]) / 2
            curr_price = (curr["high"] + curr["low"]) / 2
            if prev_price > 0:
                return ((curr_price - prev_price) / prev_price) * 100
            return None

        return None

