"""OR-logic pool backtest evaluation."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class PoolOrLogicMixin:
    """OR-logic pool backtest evaluation."""

    def _backtest_pool_or_logic(
        self, db: Session, pool_def: Dict, signal_ids: List[int], symbol: str,
        kline_min_ts: int, kline_max_ts: int, exchange: str = "hyperliquid"
    ) -> Dict[str, Any]:
        """
        Backtest pool with OR logic using pool-level edge detection.
        Triggers when pool state transitions from not-met to met (any signal satisfies).
        This matches real-time detection behavior.
        """
        signal_defs = {}
        signal_names = {}
        time_window = "5m"

        for signal_id in signal_ids:
            result = db.execute(
                text("""
                    SELECT id, signal_name, trigger_condition
                    FROM signal_definitions WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
                """),
                {"id": signal_id}
            )
            row = result.fetchone()
            if row:
                trigger_cond = row[2]
                if isinstance(trigger_cond, str):
                    try:
                        trigger_cond = json.loads(trigger_cond)
                    except json.JSONDecodeError:
                        trigger_cond = {}
                signal_defs[signal_id] = {
                    "id": row[0],
                    "signal_name": row[1],
                    "trigger_condition": trigger_cond
                }
                signal_names[signal_id] = row[1]
                time_window = trigger_cond.get("time_window", time_window)

        if not signal_defs:
            return {"error": "No valid signals in pool"}

        interval_ms = TIMEFRAME_MS.get(time_window, 300000)

        # Precompute factor signals
        factor_signals = {}
        has_non_factor = False

        metrics_data = {}
        metrics_timestamps_index = {}
        for signal_id, sig_def in signal_defs.items():
            condition = sig_def["trigger_condition"]
            metric = condition.get("metric")
            if not metric:
                continue

            if metric.startswith("factor:"):
                factor_signals[signal_id] = self._precompute_factor_for_pool(
                    db, signal_id, sig_def, symbol, kline_min_ts, kline_max_ts, exchange
                )
                continue

            has_non_factor = True
            if metric == "macd":
                continue
            if metric == "taker_volume":
                mapped_metric = "taker_ratio"
            else:
                metric_map = {"oi_delta_percent": "oi_delta", "taker_buy_ratio": "taker_ratio"}
                mapped_metric = metric_map.get(metric, metric)

            if mapped_metric not in metrics_data:
                raw_data = self._load_raw_data_for_metric(
                    db, symbol, mapped_metric, kline_min_ts, kline_max_ts, interval_ms, exchange
                )
                metrics_data[mapped_metric] = raw_data
                metrics_timestamps_index[mapped_metric] = [r[0] for r in raw_data] if raw_data else []

        # Generate check points
        all_data_timestamps = set()
        for data in metrics_data.values():
            if data:
                all_data_timestamps.update(r[0] for r in data)
        for sid, (kline_ts_list, _) in factor_signals.items():
            all_data_timestamps.update(kline_ts_list)

        if all_data_timestamps:
            data_min_ts = max(min(all_data_timestamps), kline_min_ts)
            data_max_ts = min(max(all_data_timestamps), kline_max_ts)
        else:
            data_min_ts = kline_min_ts
            data_max_ts = kline_max_ts

        if has_non_factor:
            CHECK_INTERVAL_MS = 15000
        else:
            CHECK_INTERVAL_MS = interval_ms

        start_ts = (data_min_ts // CHECK_INTERVAL_MS) * CHECK_INTERVAL_MS
        check_points = []
        current_ts = start_ts
        while current_ts <= data_max_ts:
            check_points.append(current_ts)
            current_ts += CHECK_INTERVAL_MS

        # Pre-compute all signal conditions
        signal_conditions = {sid: {} for sid in signal_defs}
        precomputed_values = {}

        for signal_id, sig_def in signal_defs.items():
            condition = sig_def["trigger_condition"]
            metric = condition.get("metric")

            # Factor signals: look up latest K-line close condition
            if metric and metric.startswith("factor:"):
                kline_ts_list, factor_conds = factor_signals.get(signal_id, ([], {}))
                if not kline_ts_list:
                    for check_time in check_points:
                        signal_conditions[signal_id][check_time] = (None, None)
                    continue
                sorted_kline_ts = sorted(factor_conds.keys())
                ki = 0
                for check_time in check_points:
                    while ki < len(sorted_kline_ts) - 1 and sorted_kline_ts[ki + 1] <= check_time:
                        ki += 1
                    if sorted_kline_ts[ki] <= check_time:
                        signal_conditions[signal_id][check_time] = factor_conds[sorted_kline_ts[ki]]
                    else:
                        signal_conditions[signal_id][check_time] = (None, None)
                continue

            if metric == "taker_volume":
                import math
                direction = condition.get("direction", "any")
                ratio_threshold = condition.get("ratio_threshold", 1.5)
                volume_threshold = condition.get("volume_threshold", 0)
                log_threshold = math.log(max(ratio_threshold, 1.01))
                raw_data = metrics_data.get("taker_ratio", [])

                if "taker_data" not in precomputed_values:
                    precomputed_values["taker_data"] = self._precompute_taker_data(
                        raw_data, interval_ms, check_points
                    )

                for check_time in check_points:
                    taker_data = precomputed_values["taker_data"].get(check_time)
                    if not taker_data:
                        signal_conditions[signal_id][check_time] = (None, None)
                        continue

                    log_ratio = taker_data["log_ratio"]
                    total = taker_data["volume"]

                    if total < volume_threshold:
                        signal_conditions[signal_id][check_time] = (False, None)
                        continue

                    condition_met = False
                    if direction == "buy" and log_ratio >= log_threshold:
                        condition_met = True
                    elif direction == "sell" and log_ratio <= -log_threshold:
                        condition_met = True
                    elif direction == "any" and abs(log_ratio) >= log_threshold:
                        condition_met = True

                    value_info = {
                        "signal_id": signal_id,
                        "signal_name": sig_def["signal_name"],
                        "value": taker_data["ratio"],
                        "threshold": ratio_threshold,
                    } if condition_met else None
                    signal_conditions[signal_id][check_time] = (condition_met, value_info)

            elif metric == "macd":
                continue

            elif metric:
                operator = condition.get("operator", "greater_than")
                threshold = condition.get("threshold", 0)
                metric_map = {"oi_delta_percent": "oi_delta", "taker_buy_ratio": "taker_ratio"}
                mapped_metric = metric_map.get(metric, metric)
                raw_data = metrics_data.get(mapped_metric, [])

                if mapped_metric not in precomputed_values:
                    precomputed_values[mapped_metric] = self._precompute_indicator_values(
                        raw_data, mapped_metric, interval_ms, check_points
                    )

                for check_time in check_points:
                    value = precomputed_values[mapped_metric].get(check_time)
                    if value is None:
                        signal_conditions[signal_id][check_time] = (None, None)
                        continue
                    condition_met = self._evaluate_condition(value, operator, threshold)
                    value_info = {
                        "signal_id": signal_id,
                        "signal_name": sig_def["signal_name"],
                        "value": value,
                        "threshold": threshold,
                    } if condition_met else None
                    signal_conditions[signal_id][check_time] = (condition_met, value_info)

        # OR Logic with Pool-Level Edge Detection
        triggers = []
        was_active = False  # Pool-level state

        for check_time in check_points:
            any_met = False
            signal_values = []

            for signal_id in signal_defs:
                result = signal_conditions[signal_id].get(check_time)
                if result is None:
                    continue
                condition_met, value_info = result
                if condition_met is None:
                    continue
                if condition_met:
                    any_met = True
                    if value_info:
                        signal_values.append(value_info)

            # Pool-level edge detection: trigger on False -> True
            if any_met and not was_active:
                triggers.append({
                    "timestamp": check_time,
                    "triggered_signals": signal_values,
                    "trigger_type": "any",
                })

            was_active = any_met

        logger.warning(f"[Backtest] OR pool {pool_def['id']} completed with {len(triggers)} triggers")
        return {
            "pool_id": pool_def["id"],
            "pool_name": pool_def["pool_name"],
            "symbol": symbol,
            "time_window": time_window,
            "logic": "OR",
            "signal_count": len(signal_ids),
            "signal_names": signal_names,
            "trigger_count": len(triggers),
            "triggers": triggers,
        }

