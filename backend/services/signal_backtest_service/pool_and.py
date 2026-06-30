"""AND-logic pool backtest evaluation."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class PoolAndLogicMixin:
    """AND-logic pool backtest evaluation."""

    def _backtest_pool_and_logic(
        self, db: Session, pool_def: Dict, signal_ids: List[int], symbol: str,
        kline_min_ts: int, kline_max_ts: int, exchange: str = "hyperliquid"
    ) -> Dict[str, Any]:
        """
        Backtest pool with AND logic using pool-level edge detection.
        Evaluates all signals at each check point simultaneously.
        """
        # Get all signal definitions
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
                # Parse trigger_condition - ORM defines as Text, so it may be string
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

        # Precompute factor signals (K-line based, separate from 15s microstructure data)
        factor_signals = {}  # signal_id -> (kline_close_ms_list, conditions_dict)
        has_non_factor = False

        # Load raw data for all metrics needed
        metrics_data = {}
        metrics_timestamps_index = {}
        for signal_id, sig_def in signal_defs.items():
            condition = sig_def["trigger_condition"]
            metric = condition.get("metric")
            if not metric:
                continue

            # Factor signals: precompute via K-line expression engine
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

        # Generate check points — pure-factor pools use K-line interval, mixed pools use 15s
        all_data_timestamps = set()
        for data in metrics_data.values():
            if data:
                all_data_timestamps.update(r[0] for r in data)

        # Add factor K-line close timestamps
        for sid, (kline_ts_list, _) in factor_signals.items():
            all_data_timestamps.update(kline_ts_list)

        if all_data_timestamps:
            data_min_ts = max(min(all_data_timestamps), kline_min_ts)
            data_max_ts = min(max(all_data_timestamps), kline_max_ts)
        else:
            data_min_ts = kline_min_ts
            data_max_ts = kline_max_ts

        if has_non_factor:
            CHECK_INTERVAL_MS = 15000  # Mixed pool: 15s granularity for microstructure data
        else:
            CHECK_INTERVAL_MS = interval_ms  # Pure factor pool: K-line interval

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

            # Factor signals: look up latest K-line close condition at each check point
            if metric and metric.startswith("factor:"):
                kline_ts_list, factor_conds = factor_signals.get(signal_id, ([], {}))
                if not kline_ts_list:
                    for check_time in check_points:
                        signal_conditions[signal_id][check_time] = (None, None)
                    continue
                sorted_kline_ts = sorted(factor_conds.keys())
                ki = 0
                for check_time in check_points:
                    # Advance to latest K-line close <= check_time
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

                if "taker_ratio" not in precomputed_values:
                    precomputed_values["taker_ratio"] = self._precompute_taker_data(
                        raw_data, interval_ms, check_points
                    )

                for check_time in check_points:
                    taker_data = precomputed_values["taker_ratio"].get(check_time)
                    if taker_data is None:
                        signal_conditions[signal_id][check_time] = (None, None)
                        continue
                    log_ratio = taker_data["log_ratio"]
                    total_volume = taker_data["volume"]
                    if direction == "buy":
                        ratio_met = log_ratio >= log_threshold
                    elif direction == "sell":
                        ratio_met = log_ratio <= -log_threshold
                    else:
                        ratio_met = abs(log_ratio) >= log_threshold
                    volume_met = total_volume >= volume_threshold
                    condition_met = ratio_met and volume_met
                    value_info = {
                        "signal_id": signal_id,
                        "signal_name": sig_def["signal_name"],
                        "metric": "taker_volume",
                        "value": taker_data["ratio"],
                        "threshold": ratio_threshold,
                        "direction": "buy" if log_ratio > 0 else "sell",
                        "ratio": taker_data["ratio"],
                        "volume": total_volume,
                        "ratio_threshold": ratio_threshold,
                        "volume_threshold": volume_threshold,
                    } if condition_met else None
                    signal_conditions[signal_id][check_time] = (condition_met, value_info)
            elif metric == "macd":
                macd_triggers = self._find_macd_triggers_in_range(
                    db, sig_def, symbol, condition.get("time_window", "15m"),
                    kline_min_ts, kline_max_ts, exchange
                )
                macd_trigger_times = {t["timestamp"]: t for t in macd_triggers}
                for check_time in check_points:
                    if check_time in macd_trigger_times:
                        t = macd_trigger_times[check_time]
                        signal_conditions[signal_id][check_time] = (True, {
                            "signal_id": signal_id,
                            "signal_name": sig_def["signal_name"],
                            "metric": "macd",
                            "triggered_event": t.get("triggered_event"),
                            "event_types": t.get("event_types"),
                            "values": t.get("values"),
                            "cross_strength": t.get("cross_strength"),
                        })
                    else:
                        signal_conditions[signal_id][check_time] = (False, None)
            elif metric:
                operator = condition.get("operator")
                threshold = condition.get("threshold")
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

        # AND Logic with Pool-Level Edge Detection (matching real-time detection)
        # Trigger when pool transitions from not-met to met (all signals satisfied)
        triggers = []
        was_active = False  # Pool-level state

        for check_time in check_points:
            all_met = True
            signal_values = []
            has_none = False

            for signal_id in signal_defs:
                result = signal_conditions[signal_id].get(check_time)
                if result is None:
                    has_none = True
                    break
                condition_met, value_info = result
                if condition_met is None:
                    has_none = True
                    break
                if not condition_met:
                    all_met = False
                elif value_info:
                    signal_values.append(value_info)

            # Skip this check point if any signal returned None
            if has_none:
                continue

            # Pool-level edge detection: trigger on False -> True
            if all_met and not was_active:
                triggers.append({
                    "timestamp": check_time,
                    "triggered_signals": signal_values,
                    "trigger_type": "all",
                })

            was_active = all_met

        return {
            "pool_id": pool_def["id"],
            "pool_name": pool_def["pool_name"],
            "symbol": symbol,
            "time_window": time_window,
            "logic": "AND",
            "signal_count": len(signal_ids),
            "signal_names": signal_names,
            "trigger_count": len(triggers),
            "triggers": triggers,
        }

