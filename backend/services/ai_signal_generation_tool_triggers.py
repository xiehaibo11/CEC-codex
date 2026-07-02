"""Trigger-finding helpers for AI signal generation tools."""
from typing import Dict, List

from sqlalchemy.orm import Session

from services.signal_backtest_service import signal_backtest_service

def _find_factor_signal_triggers(
    db: Session, symbol: str, sig: Dict,
    start_time_ms: int, current_time_ms: int, exchange: str
) -> List[int]:
    """Find factor signal trigger timestamps using K-line data and edge detection."""
    import pandas as pd
    from sqlalchemy import text
    from services.factor_resolver import compute_factor_series

    # Accept both the AI tool-call schema key ("indicator") and the canonical
    # trigger_condition key used by persisted signal_definitions rows /
    # signal_detection_service ("metric"), so predictions against real
    # seeded signals work the same as ad-hoc AI tool calls.
    metric = sig.get("metric") or sig.get("indicator") or ""
    factor_name = metric.split(":", 1)[1] if ":" in metric else metric
    operator = sig.get("operator")
    threshold = sig.get("threshold")
    tw = sig.get("time_window", "1h")

    if not all([operator, threshold is not None]):
        return {"error": f"Factor signal missing operator/threshold"}

    # Load K-lines for time range + warm-up
    from services.signal_backtest_service import TIMEFRAME_MS
    from services.factor_data_provider import get_klines_from_db
    interval_ms = TIMEFRAME_MS.get(tw, 3600000)
    warmup_ms = interval_ms * 200
    load_start_s = (start_time_ms - warmup_ms) // 1000
    end_s = current_time_ms // 1000

    klines = get_klines_from_db(db, exchange, symbol, tw, start_ts=load_start_s, end_ts=end_s)

    if len(klines) < 30:
        return {"error": f"Insufficient K-line data for factor {factor_name}"}

    series, _, err = compute_factor_series(
        db=db,
        factor_name=factor_name,
        symbol=symbol,
        period=tw,
        exchange=exchange,
        klines=klines,
    )
    if series is None or len(series) == 0:
        return {"error": err or f"Factor {factor_name} computation failed"}

    # Iterate with edge detection
    triggers = []
    was_active = False
    backtest_start_s = start_time_ms // 1000

    for idx, kline in enumerate(klines):
        ts = kline["timestamp"]
        if idx >= len(series) or pd.isna(series.iloc[idx]):
            continue
        value = float(series.iloc[idx])
        condition_met = signal_backtest_service._evaluate_condition(value, operator, threshold)
        if ts < backtest_start_s:
            was_active = condition_met
            continue
        if condition_met and not was_active:
            triggers.append(ts * 1000)
        was_active = condition_met

    return triggers


def _find_triggers_with_preloaded_data(
    raw_data: List, ts_index: List[int], metric: str,
    operator: str, threshold: float, interval_ms: int
) -> List[int]:
    """
    Find trigger timestamps using preloaded data with binary search optimization.
    Implements edge detection: only triggers on False -> True transitions.
    """
    if not raw_data:
        return []

    # Generate check points from data timestamps
    check_points = sorted(set(ts_index))
    if not check_points:
        return []

    triggers = []
    was_active = False

    for check_time in check_points:
        value = signal_backtest_service._calculate_indicator_at_time(
            raw_data, metric, check_time, interval_ms, ts_index
        )

        if value is None:
            was_active = False
            continue

        condition_met = signal_backtest_service._evaluate_condition(value, operator, threshold)

        # Edge detection: only trigger on False -> True
        if condition_met and not was_active:
            triggers.append(check_time)

        was_active = condition_met

    return triggers


def _find_taker_volume_triggers(
    raw_data: List, ts_index: List[int], direction: str,
    ratio_threshold: float, volume_threshold: float, interval_ms: int
) -> List[int]:
    """
    Find taker_volume trigger timestamps using log ratio AND volume threshold.
    Uses edge detection: only triggers on False -> True transitions.

    Both conditions must be met:
    1. Ratio condition: |log(buy/sell)| >= log(ratio_threshold) for direction
    2. Volume condition: total_volume (buy + sell) >= volume_threshold
    """
    import math

    if not raw_data:
        return []

    check_points = sorted(set(ts_index))
    if not check_points:
        return []

    # Convert ratio_threshold to log threshold
    log_threshold = math.log(max(ratio_threshold, 1.01))

    triggers = []
    was_active = False

    for check_time in check_points:
        # Get taker data including volume at this time point
        taker_data = signal_backtest_service._calc_taker_data_at_time(
            raw_data, check_time, interval_ms
        )

        if taker_data is None:
            was_active = False
            continue

        log_ratio = taker_data["log_ratio"]
        total_volume = taker_data["volume"]

        # Check BOTH ratio and volume conditions
        ratio_met = False
        if direction == "buy":
            ratio_met = log_ratio >= log_threshold
        elif direction == "sell":
            ratio_met = log_ratio <= -log_threshold
        elif direction == "any":
            ratio_met = abs(log_ratio) >= log_threshold

        volume_met = total_volume >= volume_threshold
        condition_met = ratio_met and volume_met

        # Edge detection: only trigger on False -> True
        if condition_met and not was_active:
            triggers.append(check_time)

        was_active = condition_met

    return triggers
