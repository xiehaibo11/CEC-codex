"""Range-scan trigger detection for individual metrics and factors."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class TriggerRangeMixin:
    """Range-scan trigger detection for individual metrics and factors."""

    def _find_triggers_in_range(
        self, db: Session, signal_def: Dict, symbol: str, time_window: str,
        kline_min_ts: int = None, kline_max_ts: int = None,
        exchange: str = "hyperliquid"
    ) -> List[Dict]:
        """
        Find trigger points within a time range using 15-second sliding window detection.

        This simulates real-time detection behavior:
        - Check every 15 seconds (matching data collection granularity)
        - At each check point, calculate indicator using data available at that moment
        - Apply edge detection: only trigger on False -> True transitions

        Args:
            db: Database session
            signal_def: Signal definition dict
            symbol: Trading symbol
            time_window: Time window (e.g., '5m', '15m')
            kline_min_ts: Minimum timestamp in milliseconds (optional)
            kline_max_ts: Maximum timestamp in milliseconds (optional)
        """
        condition = signal_def.get("trigger_condition", {})
        metric = condition.get("metric")
        operator = condition.get("operator")
        threshold = condition.get("threshold")

        logger.warning(f"[Backtest] _find_triggers_in_range: symbol={symbol}, metric={metric}, "
                       f"operator={operator}, threshold={threshold}, time_window={time_window}, exchange={exchange}")

        # Handle taker_volume composite signal
        if metric == "taker_volume":
            logger.warning(f"[Backtest] Using taker_volume composite signal handler")
            return self._find_taker_triggers_in_range(
                db, signal_def, symbol, time_window, kline_min_ts, kline_max_ts, exchange
            )

        # Handle MACD event-based signal
        if metric == "macd":
            logger.warning(f"[Backtest] Using MACD event-based signal handler")
            return self._find_macd_triggers_in_range(
                db, signal_def, symbol, time_window, kline_min_ts, kline_max_ts, exchange
            )

        # Handle factor-based signal
        if metric and metric.startswith("factor:"):
            logger.warning(f"[Backtest] Using factor signal handler for {metric}")
            return self._find_factor_triggers_in_range(
                db, signal_def, symbol, time_window, kline_min_ts, kline_max_ts, exchange
            )

        # Handle oi USD change signal (special: calculates USD value change)
        if metric == "oi":
            logger.warning(f"[Backtest] Using oi USD change signal handler")
            return self._find_oi_change_triggers_in_range(
                db, signal_def, symbol, time_window, kline_min_ts, kline_max_ts, exchange
            )

        if not all([metric, operator, threshold is not None]):
            logger.warning(f"[Backtest] Missing required fields: metric={metric}, "
                           f"operator={operator}, threshold={threshold}")
            return []

        # Map metric names for backward compatibility
        metric_map = {
            "oi_delta_percent": "oi_delta",
            "funding_rate": "funding",
            "taker_buy_ratio": "taker_ratio",
        }
        mapped_metric = metric_map.get(metric, metric)
        if mapped_metric != metric:
            logger.warning(f"[Backtest] Metric mapped: {metric} -> {mapped_metric}")
        metric = mapped_metric

        interval_ms = TIMEFRAME_MS.get(time_window, 300000)
        check_interval_ms = 15000  # 15 seconds, matching data granularity

        # Load raw 15-second granularity data for the time range
        raw_data = self._load_raw_data_for_metric(
            db, symbol, metric, kline_min_ts, kline_max_ts, interval_ms, exchange
        )
        if not raw_data:
            logger.warning(f"[Backtest] NO DATA returned from _load_raw_data_for_metric "
                           f"for {symbol}/{metric}")
            return []
        logger.warning(f"[Backtest] Loaded {len(raw_data)} raw data points for {symbol}/{metric}")

        # Generate check points every 15 seconds
        check_points = self._generate_check_points(
            raw_data, kline_min_ts, kline_max_ts, check_interval_ms
        )

        # Simulate real-time detection with edge triggering
        triggers = []
        was_active = False

        # Build timestamps index for O(log n) binary search optimization
        timestamps_index = [r[0] for r in raw_data]

        for check_time in check_points:
            # Calculate indicator value at this check point (using only data up to check_time)
            value = self._calculate_indicator_at_time(
                raw_data, metric, check_time, interval_ms, timestamps_index
            )

            if value is None:
                continue

            # Check condition
            condition_met = self._evaluate_condition(value, operator, threshold)

            # Edge detection: only trigger on False -> True
            if condition_met and not was_active:
                triggers.append({
                    "timestamp": check_time,
                    "value": value,
                    "threshold": threshold,
                    "operator": operator,
                })

            was_active = condition_met

        return triggers

    def _find_oi_change_triggers_in_range(
        self, db: Session, signal_def: Dict, symbol: str, time_window: str,
        kline_min_ts: int = None, kline_max_ts: int = None,
        exchange: str = "hyperliquid"
    ) -> List[Dict]:
        """
        Find OI USD change signal triggers.

        OI change measures the absolute USD value change in open interest.
        Formula: (current_OI - previous_OI) × mark_price
        Returns USD value (can be positive or negative).
        """
        from database.models import MarketAssetMetrics
        from datetime import datetime

        condition = signal_def.get("trigger_condition", {})
        operator = condition.get("operator")
        threshold = condition.get("threshold")

        interval_ms = TIMEFRAME_MS.get(time_window, 300000)

        # Load data for backtest range + one extra interval for first change calc
        current_time_ms = kline_max_ts or int(datetime.utcnow().timestamp() * 1000)
        start_time_ms = (kline_min_ts or current_time_ms - 24*60*60*1000) - interval_ms

        records = db.query(
            MarketAssetMetrics.timestamp,
            MarketAssetMetrics.open_interest,
            MarketAssetMetrics.mark_price
        ).filter(
            MarketAssetMetrics.exchange == exchange,
            MarketAssetMetrics.symbol == symbol.upper(),
            MarketAssetMetrics.timestamp >= start_time_ms,
            MarketAssetMetrics.timestamp <= current_time_ms,
            MarketAssetMetrics.open_interest.isnot(None),
            MarketAssetMetrics.mark_price.isnot(None)
        ).order_by(MarketAssetMetrics.timestamp).all()

        if not records:
            logger.warning(f"[Backtest] No OI data for {symbol}")
            return []

        # Aggregate by interval bucket
        buckets = {}
        for ts, oi, price in records:
            bucket_ts = (ts // interval_ms) * interval_ms
            buckets[bucket_ts] = (float(oi), float(price))

        sorted_times = sorted(buckets.keys())
        if len(sorted_times) < 2:
            return []

        logger.warning(f"[Backtest] Loaded {len(buckets)} OI buckets for USD change calc")

        # Calculate USD changes and find triggers
        triggers = []
        was_active = False
        backtest_start = kline_min_ts or sorted_times[1]

        for i in range(1, len(sorted_times)):
            check_time = sorted_times[i]
            if check_time < backtest_start:
                continue

            curr_oi, curr_price = buckets[sorted_times[i]]
            prev_oi, _ = buckets[sorted_times[i-1]]
            change_usd = (curr_oi - prev_oi) * curr_price

            # Evaluate condition
            condition_met = self._evaluate_condition(change_usd, operator, threshold)

            # Edge detection
            if condition_met and not was_active:
                triggers.append({
                    "timestamp": check_time,
                    "value": round(change_usd, 2),
                    "threshold": threshold,
                    "operator": operator,
                })

            was_active = condition_met

        return triggers

    def _find_factor_triggers_in_range(
        self, db: Session, signal_def: Dict, symbol: str, time_window: str,
        kline_min_ts: int = None, kline_max_ts: int = None,
        exchange: str = "hyperliquid"
    ) -> List[Dict]:
        """
        Find factor signal triggers using K-line close timestamps.

        Factor values only change when a new K-line closes. We:
        1. Load historical K-lines for the backtest range
        2. Run expression engine once on the full series
        3. Iterate each K-line close timestamp with edge detection
        """
        from services.factor_resolver import compute_factor_series
        import pandas as pd

        condition = signal_def.get("trigger_condition", {})
        metric = condition.get("metric", "")
        operator = condition.get("operator")
        threshold = condition.get("threshold")
        factor_name = metric.split(":", 1)[1] if ":" in metric else metric

        if not all([operator, threshold is not None]):
            return []

        # Load K-lines for backtest range with 200-bar warm-up
        from services.factor_data_provider import get_klines_from_db
        interval_ms = TIMEFRAME_MS.get(time_window, 3600000)
        warmup_ms = interval_ms * 200
        load_start = (kline_min_ts or 0) - warmup_ms

        klines = get_klines_from_db(
            db, exchange, symbol, time_window,
            start_ts=load_start // 1000,
            end_ts=(kline_max_ts or int(datetime.utcnow().timestamp() * 1000)) // 1000,
        )

        if len(klines) < 30:
            logger.warning(f"[Backtest] Insufficient K-line data for factor {factor_name}: {len(klines)} bars")
            return []

        # Run factor computation once on full series
        series, _, err = compute_factor_series(
            db=db,
            factor_name=factor_name,
            symbol=symbol,
            period=time_window,
            exchange=exchange,
            klines=klines,
        )
        if series is None or len(series) == 0:
            logger.warning(f"[Backtest] Factor {factor_name} execution failed: {err}")
            return []

        logger.warning(f"[Backtest] Factor {factor_name}: computed {len(series)} values "
                       f"from {len(klines)} K-lines")

        # Iterate K-line close timestamps with edge detection
        triggers = []
        was_active = False
        backtest_start_s = (kline_min_ts or 0) // 1000

        for i, kline in enumerate(klines):
            ts = kline["timestamp"]
            # Only check within backtest range
            if ts < backtest_start_s:
                # Still update was_active for warm-up edge detection
                if i < len(series) and not pd.isna(series.iloc[i]):
                    val = float(series.iloc[i])
                    was_active = self._evaluate_condition(val, operator, threshold)
                continue

            if i >= len(series) or pd.isna(series.iloc[i]):
                continue

            value = float(series.iloc[i])
            condition_met = self._evaluate_condition(value, operator, threshold)

            # Edge detection: False -> True
            if condition_met and not was_active:
                triggers.append({
                    "timestamp": ts * 1000,  # Convert back to ms
                    "value": value,
                    "threshold": threshold,
                    "operator": operator,
                })

            was_active = condition_met

        logger.warning(f"[Backtest] Factor {factor_name}: found {len(triggers)} triggers")
        return triggers

    def _precompute_factor_for_pool(
        self, db: Session, signal_id: int, sig_def: Dict, symbol: str,
        kline_min_ts: int, kline_max_ts: int, exchange: str
    ) -> tuple:
        """Precompute factor condition at each K-line close for pool backtest.

        Returns:
            (kline_close_ms_list, conditions_dict)
            - kline_close_ms_list: sorted list of K-line close timestamps (ms)
            - conditions_dict: {ts_ms: (condition_met, value_info)}
              The condition persists until the next K-line close.
        """
        from services.factor_resolver import compute_factor_series
        from services.factor_data_provider import get_klines_from_db
        import pandas as pd

        condition = sig_def["trigger_condition"]
        metric = condition.get("metric", "")
        operator = condition.get("operator")
        threshold = condition.get("threshold")
        time_window = condition.get("time_window", "1h")
        factor_name = metric.split(":", 1)[1] if ":" in metric else metric

        if not all([operator, threshold is not None]):
            return ([], {})

        interval_ms = TIMEFRAME_MS.get(time_window, 3600000)
        warmup_ms = interval_ms * 200
        load_start = (kline_min_ts or 0) - warmup_ms

        klines = get_klines_from_db(
            db, exchange, symbol, time_window,
            start_ts=load_start // 1000,
            end_ts=(kline_max_ts or int(datetime.utcnow().timestamp() * 1000)) // 1000,
        )
        if len(klines) < 30:
            return ([], {})

        series, _, err = compute_factor_series(
            db=db,
            factor_name=factor_name,
            symbol=symbol,
            period=time_window,
            exchange=exchange,
            klines=klines,
        )
        if series is None or len(series) == 0:
            return ([], {})

        backtest_start_s = (kline_min_ts or 0) // 1000
        kline_close_ms_list = []
        conditions = {}

        for i, kline in enumerate(klines):
            ts_s = kline["timestamp"]
            if i >= len(series) or pd.isna(series.iloc[i]):
                continue
            value = float(series.iloc[i])
            condition_met = self._evaluate_condition(value, operator, threshold)
            ts_ms = ts_s * 1000
            if ts_s >= backtest_start_s:
                kline_close_ms_list.append(ts_ms)
            value_info = {
                "signal_id": signal_id,
                "signal_name": sig_def["signal_name"],
                "value": value,
                "threshold": threshold,
                "operator": operator,
            } if condition_met else None
            conditions[ts_ms] = (condition_met, value_info)

        return (kline_close_ms_list, conditions)

    def _find_taker_triggers_in_range(
        self, db: Session, signal_def: Dict, symbol: str, time_window: str,
        kline_min_ts: int = None, kline_max_ts: int = None,
        exchange: str = "hyperliquid"
    ) -> List[Dict]:
        """
        Find taker_volume composite signal triggers using 15-second sliding window.
        Simulates real-time detection with edge triggering.
        """
        condition = signal_def.get("trigger_condition", {})
        direction = condition.get("direction", "any")
        ratio_threshold = condition.get("ratio_threshold", 1.5)
        volume_threshold = condition.get("volume_threshold", 0)

        interval_ms = TIMEFRAME_MS.get(time_window, 300000)

        # Load raw 15-second granularity data
        raw_data = self._load_raw_data_for_metric(
            db, symbol, "taker_ratio", kline_min_ts, kline_max_ts, interval_ms, exchange
        )
        if not raw_data:
            return []

        # Generate check points every 15 seconds
        check_points = self._generate_check_points(raw_data, kline_min_ts, kline_max_ts, 15000)

        # Simulate real-time detection with edge triggering
        triggers = []
        was_active = False

        import math
        # Convert user's ratio threshold to log threshold
        log_threshold = math.log(max(ratio_threshold, 1.01))

        # Build timestamps index for O(log n) binary search optimization
        timestamps_index = [r[0] for r in raw_data]

        for check_time in check_points:
            # Calculate taker data at this check point
            taker_data = self._calc_taker_data_at_time(raw_data, check_time, interval_ms, timestamps_index)
            if not taker_data:
                continue

            log_ratio = taker_data["log_ratio"]
            ratio = taker_data["ratio"]  # Original ratio for display
            total = taker_data["volume"]

            if total < volume_threshold:
                was_active = False
                continue

            # Check condition using log ratio (symmetric around 0)
            condition_met = False
            actual_dir = None

            if direction == "buy" and log_ratio >= log_threshold:
                condition_met, actual_dir = True, "buy"
            elif direction == "sell" and log_ratio <= -log_threshold:
                condition_met, actual_dir = True, "sell"
            elif direction == "any":
                if log_ratio >= log_threshold:
                    condition_met, actual_dir = True, "buy"
                elif log_ratio <= -log_threshold:
                    condition_met, actual_dir = True, "sell"

            # Edge detection: only trigger on False -> True
            if condition_met and not was_active:
                triggers.append({
                    "timestamp": check_time,
                    "direction": actual_dir,
                    "log_ratio": log_ratio,
                    "ratio": ratio,  # Original ratio for display
                    "ratio_threshold": ratio_threshold,
                    "volume": total,
                    "volume_threshold": volume_threshold,
                })

            was_active = condition_met

        return triggers

