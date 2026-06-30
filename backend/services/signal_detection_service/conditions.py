"""
Signal Detection Service - condition and trigger checking logic.

Edge-triggered condition evaluation for individual signals.
"""

import logging
import time
from typing import Dict, Optional, Any

from .states import SignalState

logger = logging.getLogger(__name__)


class ConditionCheckMixin:
    """Mixin providing per-signal condition and trigger checks."""

    def _check_signal_condition(
        self, signal_id: int, signal_def: dict, symbol: str, market_data: Dict[str, Any]
    ) -> Optional[dict]:
        """
        Check if a signal's condition is met (without edge detection).
        Returns condition details including whether it's met.
        """
        condition = signal_def.get("trigger_condition", {})
        metric = condition.get("metric")
        time_window = condition.get("time_window", "5m")
        exchange = signal_def.get("exchange", "hyperliquid")

        if not metric:
            return None

        # Handle taker_volume composite signal
        if metric == "taker_volume":
            return self._check_taker_condition(signal_id, signal_def, symbol, condition, time_window, exchange)

        # Handle MACD event-based signal
        if metric == "macd":
            return self._check_macd_condition(signal_id, signal_def, symbol, condition, time_window, exchange)

        # Standard single-value signal
        operator = condition.get("operator")
        threshold = condition.get("threshold")

        if not all([operator, threshold is not None]):
            return None

        current_value = self._get_metric_value(metric, symbol, market_data, time_window, exchange)
        if current_value is None:
            return None

        condition_met = self._evaluate_condition(current_value, operator, threshold)

        # DEBUG LOG: Standard signal condition check (all exchanges, all metrics)
        print(f"[SignalCheck] signal={signal_id} symbol={symbol} metric={metric} exchange={exchange} period={time_window} value={current_value:.6f} op={operator} thresh={threshold} met={condition_met}", flush=True)

        result = {
            "signal_id": signal_id,
            "signal_name": signal_def.get("signal_name"),
            "description": signal_def.get("description"),
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "current_value": current_value,
            "condition_met": condition_met,
            "time_window": time_window,
            "exchange": exchange,
        }

        # Enrich factor metrics with effectiveness data (IC/ICIR/win_rate/decay)
        if metric.startswith("factor:") and condition_met:
            self._enrich_factor_effectiveness(result, metric, symbol, exchange)

        return result

    def _check_signal_trigger(
        self, signal_id: int, signal_def: dict, symbol: str, market_data: Dict[str, Any]
    ) -> Optional[dict]:
        """
        Check if a signal should trigger based on current market data.
        Implements edge-triggered logic.
        """
        condition = signal_def.get("trigger_condition", {})
        metric = condition.get("metric")
        time_window = condition.get("time_window", "5m")
        exchange = signal_def.get("exchange", "hyperliquid")

        if not metric:
            return None

        # Handle taker_volume composite signal
        if metric == "taker_volume":
            return self._check_taker_volume_trigger(
                signal_id, signal_def, symbol, condition, time_window, exchange
            )

        # Standard single-value signal
        operator = condition.get("operator")
        threshold = condition.get("threshold")

        if not all([operator, threshold is not None]):
            return None

        # Get current metric value
        current_value = self._get_metric_value(metric, symbol, market_data, time_window, exchange)
        if current_value is None:
            return None

        # Check condition
        condition_met = self._evaluate_condition(current_value, operator, threshold)

        # Get or create signal state
        state_key = (signal_id, symbol)
        if state_key not in self.signal_states:
            self.signal_states[state_key] = SignalState(
                signal_id=signal_id, symbol=symbol
            )
        state = self.signal_states[state_key]

        # Edge detection: only trigger when condition changes from False to True
        was_active = state.is_active
        should_trigger = condition_met and not was_active

        # Update state
        state.is_active = condition_met
        state.last_value = current_value
        state.last_check_time = time.time()

        # Debug logging for edge detection (using INFO level for visibility)
        if condition_met:
            logger.info(
                f"[EdgeTrigger] {signal_def.get('signal_name')} on {symbol}: "
                f"value={current_value:.4f}, threshold={threshold}, "
                f"was_active={was_active}, is_active={condition_met}, trigger={should_trigger}"
            )

        if should_trigger:
            trigger_result = {
                "signal_id": signal_id,
                "signal_name": signal_def.get("signal_name"),
                "symbol": symbol,
                "trigger_value": current_value,
                "threshold": threshold,
                "operator": operator,
                "metric": metric,
                "trigger_time": time.time(),
                "description": signal_def.get("description"),
            }

            # For funding metric, add current rate context
            if metric in ("funding", "funding_rate"):
                current_rate = self._get_funding_current_rate(symbol, time_window)
                if current_rate is not None:
                    trigger_result["current_rate"] = current_rate

            self._log_trigger(trigger_result)
            return trigger_result

        return None

    def _check_taker_condition(
        self, signal_id: int, signal_def: dict, symbol: str, condition: dict, time_window: str,
        exchange: str = "hyperliquid"
    ) -> Optional[dict]:
        """Check taker_volume condition (without edge detection)."""
        direction = condition.get("direction", "any")
        ratio_threshold = condition.get("ratio_threshold", 1.5)
        volume_threshold = condition.get("volume_threshold", 0)

        from database.connection import SessionLocal
        from services.market_flow_indicators import _get_taker_data, TIMEFRAME_MS
        from datetime import datetime

        period = time_window if isinstance(time_window, str) else self._time_window_to_period(time_window)
        if period not in TIMEFRAME_MS:
            return None

        interval_ms = TIMEFRAME_MS[period]
        current_time_ms = int(datetime.utcnow().timestamp() * 1000)

        # For Binance, include debug snapshot for troubleshooting
        include_debug = (exchange == "binance")

        db = SessionLocal()
        try:
            taker_data = _get_taker_data(db, symbol, period, interval_ms, current_time_ms, exchange, include_debug)
        finally:
            db.close()

        if not taker_data:
            return None

        buy = taker_data.get("buy", 0)
        sell = taker_data.get("sell", 0)
        total = buy + sell

        condition_met = False
        actual_direction = None
        actual_ratio = None

        if total >= volume_threshold and sell > 0:
            actual_ratio = buy / sell
            if direction == "buy" and actual_ratio >= ratio_threshold:
                condition_met = True
                actual_direction = "buy"
            elif direction == "sell" and actual_ratio <= 1 / ratio_threshold:
                condition_met = True
                actual_direction = "sell"
            elif direction == "any":
                if actual_ratio >= ratio_threshold:
                    condition_met = True
                    actual_direction = "buy"
                elif actual_ratio <= 1 / ratio_threshold:
                    condition_met = True
                    actual_direction = "sell"

        # DEBUG LOG: Taker volume condition check (all exchanges)
        ratio_str = f"{actual_ratio:.4f}" if actual_ratio else "N/A"
        print(f"[TakerCheck] signal={signal_id} symbol={symbol} exchange={exchange} period={period} ts={current_time_ms} buy={buy:.2f} sell={sell:.2f} ratio={ratio_str} met={condition_met}", flush=True)

        result = {
            "signal_id": signal_id,
            "signal_name": signal_def.get("signal_name"),
            "metric": "taker_volume",
            "condition_met": condition_met,
            "direction": actual_direction or direction,
            "buy": buy,
            "sell": sell,
            "total": total,
            "ratio": actual_ratio,
            "ratio_threshold": ratio_threshold,
            "volume_threshold": volume_threshold,
            "time_window": time_window,
            "exchange": exchange,
        }

        # Include debug snapshot for Binance
        if include_debug and "debug_snapshot" in taker_data:
            result["debug_snapshot"] = taker_data["debug_snapshot"]

        return result

    def _check_macd_condition(
        self, signal_id: int, signal_def: dict, symbol: str, condition: dict, time_window: str,
        exchange: str = "hyperliquid"
    ) -> Optional[dict]:
        """
        Check MACD event-based condition (without edge detection).
        Supports multiple event types: golden_cross, death_cross, histogram_positive,
        histogram_negative, macd_above_zero, macd_below_zero.
        """
        from database.connection import SessionLocal
        from services.technical_indicators import get_macd_for_signal
        from datetime import datetime

        event_types = condition.get("event_types", [])
        if not event_types:
            return None

        period = time_window if isinstance(time_window, str) else self._time_window_to_period(time_window)
        current_time_ms = int(datetime.utcnow().timestamp() * 1000)

        db = SessionLocal()
        try:
            macd_data = get_macd_for_signal(db, symbol, period, current_time_ms, exchange)
        finally:
            db.close()

        if not macd_data:
            return None

        curr = macd_data['current']
        prev = macd_data['previous']

        # Check each event type
        triggered_event = None
        condition_met = False

        for event_type in event_types:
            if event_type == "golden_cross":
                # Golden cross: histogram crosses from negative to positive
                if prev['histogram'] <= 0 and curr['histogram'] > 0:
                    triggered_event = "golden_cross"
                    condition_met = True
                    break
            elif event_type == "death_cross":
                # Death cross: histogram crosses from positive to negative
                if prev['histogram'] >= 0 and curr['histogram'] < 0:
                    triggered_event = "death_cross"
                    condition_met = True
                    break
            elif event_type == "histogram_positive":
                # Histogram turns positive (same as golden cross)
                if prev['histogram'] <= 0 and curr['histogram'] > 0:
                    triggered_event = "histogram_positive"
                    condition_met = True
                    break
            elif event_type == "histogram_negative":
                # Histogram turns negative (same as death cross)
                if prev['histogram'] >= 0 and curr['histogram'] < 0:
                    triggered_event = "histogram_negative"
                    condition_met = True
                    break
            elif event_type == "macd_above_zero":
                # MACD line crosses above zero
                if prev['macd'] <= 0 and curr['macd'] > 0:
                    triggered_event = "macd_above_zero"
                    condition_met = True
                    break
            elif event_type == "macd_below_zero":
                # MACD line crosses below zero
                if prev['macd'] >= 0 and curr['macd'] < 0:
                    triggered_event = "macd_below_zero"
                    condition_met = True
                    break

        # DEBUG LOG
        print(f"[MACDCheck] signal={signal_id} symbol={symbol} exchange={exchange} period={period} "
              f"events={event_types} curr_hist={curr['histogram']:.6f} prev_hist={prev['histogram']:.6f} "
              f"triggered={triggered_event} met={condition_met}", flush=True)

        return {
            "signal_id": signal_id,
            "signal_name": signal_def.get("signal_name"),
            "description": signal_def.get("description"),
            "metric": "macd",
            "event_types": event_types,
            "triggered_event": triggered_event,
            "condition_met": condition_met,
            "time_window": time_window,
            "exchange": exchange,
            "values": {
                "macd": curr['macd'],
                "signal": curr['signal'],
                "histogram": curr['histogram'],
                "prev_macd": prev['macd'],
                "prev_signal": prev['signal'],
                "prev_histogram": prev['histogram'],
            },
            "cross_strength": macd_data['cross_strength'],
            "latest_kline_ts": macd_data['latest_kline_ts'],
        }

    def _check_taker_volume_trigger(
        self, signal_id: int, signal_def: dict, symbol: str, condition: dict, time_window: str,
        exchange: str = "hyperliquid"
    ) -> Optional[dict]:
        """
        Check taker_volume composite signal trigger.
        Uses log(buy/sell) for symmetric ratio detection.
        Condition format:
        {
            "metric": "taker_volume",
            "direction": "buy" | "sell" | "any",
            "ratio_threshold": 1.5,  # User sets multiplier, internally converted to log
            "volume_threshold": 50000,
            "time_window": "5m"
        }
        """
        import math
        direction = condition.get("direction", "any")
        ratio_threshold = condition.get("ratio_threshold", 1.5)
        volume_threshold = condition.get("volume_threshold", 0)

        # Convert user's ratio threshold to log threshold
        # e.g., 1.5 -> log(1.5) = 0.405, so we check if |log_ratio| >= 0.405
        log_threshold = math.log(max(ratio_threshold, 1.01))  # Prevent log(1) = 0

        # Get taker data from DB
        from database.connection import SessionLocal
        from services.market_flow_indicators import _get_taker_data, TIMEFRAME_MS
        from datetime import datetime

        period = time_window if isinstance(time_window, str) else self._time_window_to_period(time_window)
        if period not in TIMEFRAME_MS:
            return None

        interval_ms = TIMEFRAME_MS[period]
        current_time_ms = int(datetime.utcnow().timestamp() * 1000)

        db = SessionLocal()
        try:
            taker_data = _get_taker_data(db, symbol, period, interval_ms, current_time_ms, exchange)
        finally:
            db.close()

        if not taker_data:
            return None

        buy = taker_data.get("buy", 0)
        sell = taker_data.get("sell", 0)
        total = buy + sell

        # Check volume threshold
        if total < volume_threshold:
            return None

        # Check direction and log ratio
        # Log ratio = ln(buy/sell), symmetric around 0
        # >0 means buyers dominate, <0 means sellers dominate
        condition_met = False
        actual_direction = None
        log_ratio = None

        if buy > 0 and sell > 0:
            log_ratio = math.log(buy / sell)

            if direction == "buy":
                # Buy dominant: log_ratio >= log_threshold
                if log_ratio >= log_threshold:
                    condition_met = True
                    actual_direction = "buy"
            elif direction == "sell":
                # Sell dominant: log_ratio <= -log_threshold (symmetric)
                if log_ratio <= -log_threshold:
                    condition_met = True
                    actual_direction = "sell"
            elif direction == "any":
                # Either direction dominant (using abs for symmetry)
                if log_ratio >= log_threshold:
                    condition_met = True
                    actual_direction = "buy"
                elif log_ratio <= -log_threshold:
                    condition_met = True
                    actual_direction = "sell"

        # Edge detection
        state_key = (signal_id, symbol)
        if state_key not in self.signal_states:
            self.signal_states[state_key] = SignalState(signal_id=signal_id, symbol=symbol)
        state = self.signal_states[state_key]

        should_trigger = condition_met and not state.is_active

        state.is_active = condition_met
        state.last_value = log_ratio
        state.last_check_time = time.time()

        if should_trigger and actual_direction and log_ratio is not None:
            trigger_result = {
                "signal_id": signal_id,
                "signal_name": signal_def.get("signal_name"),
                "symbol": symbol,
                "metric": "taker_volume",
                "trigger_time": time.time(),
                "description": signal_def.get("description"),
                # Taker volume specific fields
                "actual_direction": actual_direction,
                "buy": buy,
                "sell": sell,
                "total": total,
                "log_ratio": log_ratio,  # Log transformed ratio
                "ratio": buy / sell,  # Original ratio for display
                "ratio_threshold": ratio_threshold,
                "volume_threshold": volume_threshold,
            }
            self._log_taker_volume_trigger(trigger_result)
            return trigger_result

        return None

    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate if a condition is met.

        Supports both symbol and text forms of operators for compatibility
        with AI-generated signal configs.
        """
        # Support both symbol and text forms of operators
        if operator in (">", "greater_than", "gt"):
            return value > threshold
        elif operator in (">=", "greater_than_or_equal", "gte"):
            return value >= threshold
        elif operator in ("<", "less_than", "lt"):
            return value < threshold
        elif operator in ("<=", "less_than_or_equal", "lte"):
            return value <= threshold
        elif operator in ("==", "equal", "eq"):
            return abs(value - threshold) < 1e-9
        elif operator in ("!=", "not_equal", "ne"):
            return abs(value - threshold) >= 1e-9
        elif operator in ("abs_greater_than", "abs_gt"):
            return abs(value) > threshold
        elif operator in ("abs_less_than", "abs_lt"):
            return abs(value) < threshold
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
