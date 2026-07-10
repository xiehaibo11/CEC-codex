"""Completed-bar multi-timeframe snapshots for production event signals."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List

TIMEFRAME_MINUTES = {
    "4h": 240,
    "30m": 30,
    "15m": 15,
    "10m": 10,
    "5m": 5,
}


def build_timeframe_bars(
    one_minute_bars: Iterable[Dict[str, Any]],
    timeframe: str,
    *,
    now_ts: int | None = None,
) -> List[Dict[str, Any]]:
    """Aggregate complete UTC-aligned bars from closed 1m candles.

    A bucket is accepted only when it has every expected 1m timestamp and its
    close is not in the future relative to ``now_ts``. Missing bars therefore
    fail closed instead of being silently forward-filled into an AI signal.
    """
    minutes = TIMEFRAME_MINUTES.get(timeframe)
    if minutes is None:
        raise ValueError(f"Unsupported production timeframe: {timeframe}")

    interval = minutes * 60
    expected = minutes
    groups: dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for raw in sorted(one_minute_bars, key=lambda item: int(item["timestamp"])):
        timestamp = int(raw["timestamp"])
        bucket = timestamp - timestamp % interval
        groups[bucket].append(raw)

    result: List[Dict[str, Any]] = []
    for bucket, rows in sorted(groups.items()):
        timestamps = [int(row["timestamp"]) for row in rows]
        complete = (
            len(rows) == expected
            and timestamps == list(range(bucket, bucket + interval, 60))
            and (now_ts is None or bucket + interval <= int(now_ts))
        )
        if not complete:
            continue
        result.append(
            {
                "timestamp": bucket,
                "open": float(rows[0]["open"]),
                "high": max(float(row["high"]) for row in rows),
                "low": min(float(row["low"]) for row in rows),
                "close": float(rows[-1]["close"]),
                "volume": sum(float(row.get("volume") or 0.0) for row in rows),
                "bar_count": len(rows),
                "timeframe": timeframe,
            }
        )
    return result


def _direction(bars: List[Dict[str, Any]]) -> tuple[str, float]:
    if len(bars) < 2 or not bars[-2]["close"]:
        return "hold", 0.0
    return_pct = (bars[-1]["close"] - bars[-2]["close"]) / bars[-2]["close"] * 100.0
    if return_pct > 0.01:
        return "long", round(return_pct, 6)
    if return_pct < -0.01:
        return "short", round(return_pct, 6)
    return "hold", round(return_pct, 6)


def _ema(values: List[float], span: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (span + 1.0)
    current = float(values[0])
    for value in values[1:]:
        current = alpha * float(value) + (1.0 - alpha) * current
    return round(current, 8)


def _indicator_snapshot(bars: List[Dict[str, Any]]) -> Dict[str, float | None]:
    """Small, deterministic indicator set for the professional prompt."""
    closes = [float(item["close"]) for item in bars]
    if not closes:
        return {"ema_fast": None, "ema_slow": None, "rsi": None, "atr_pct": None}

    gains: List[float] = []
    losses: List[float] = []
    true_ranges: List[float] = []
    previous_close = closes[0]
    for item, close in zip(bars, closes):
        change = close - previous_close
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
        true_ranges.append(
            max(
                float(item["high"]) - float(item["low"]),
                abs(float(item["high"]) - previous_close),
                abs(float(item["low"]) - previous_close),
            )
        )
        previous_close = close
    window = min(14, len(closes))
    avg_gain = sum(gains[-window:]) / window
    avg_loss = sum(losses[-window:]) / window
    if avg_loss == 0:
        rsi = 100.0 if avg_gain > 0 else 50.0
    else:
        rsi = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    atr = sum(true_ranges[-window:]) / window
    return {
        "ema_fast": _ema(closes, 5),
        "ema_slow": _ema(closes, 20),
        "rsi": round(rsi, 4),
        "atr_pct": round(atr / closes[-1] * 100.0, 6) if closes[-1] else 0.0,
    }


def build_multi_timeframe_snapshot(
    one_minute_bars: Iterable[Dict[str, Any]],
    *,
    now_ts: int | None = None,
    min_bars: int = 2,
) -> Dict[str, Any]:
    """Return the five production timeframes and a fail-closed alignment verdict."""
    source = list(one_minute_bars)
    timeframes: Dict[str, Dict[str, Any]] = {}
    directions: Dict[str, str] = {}

    for timeframe in TIMEFRAME_MINUTES:
        bars = build_timeframe_bars(source, timeframe, now_ts=now_ts)
        if len(bars) < min_bars:
            timeframes[timeframe] = {
                "timeframe": timeframe,
                "status": "insufficient_history",
                "direction": "hold",
                "return_pct": 0.0,
                "bar_count": len(bars),
                "bars": bars[-min_bars:],
                **_indicator_snapshot(bars),
            }
            directions[timeframe] = "hold"
            continue
        direction, return_pct = _direction(bars)
        timeframes[timeframe] = {
            "timeframe": timeframe,
            "status": "ready",
            "direction": direction,
            "return_pct": return_pct,
            "bar_count": len(bars),
            "bars": bars[-min_bars:],
            **_indicator_snapshot(bars),
        }
        directions[timeframe] = direction

    non_hold = {direction for direction in directions.values() if direction != "hold"}
    all_ready = all(item["status"] == "ready" for item in timeframes.values())
    aligned_direction = "hold"
    if all_ready and len(non_hold) == 1:
        aligned_direction = next(iter(non_hold))

    return {
        "timeframes": timeframes,
        "directions": directions,
        "aligned_direction": aligned_direction,
        "conflict": not all_ready or len(non_hold) > 1,
        "required_timeframes": list(TIMEFRAME_MINUTES),
    }
