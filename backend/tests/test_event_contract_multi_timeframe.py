"""Multi-timeframe snapshots use only completed 1m bars."""

from __future__ import annotations

from services.event_contract.multi_timeframe import (
    build_multi_timeframe_snapshot,
    build_timeframe_bars,
)


def _bars(minutes: int, *, slope: float = 0.01):
    rows = []
    for index in range(minutes):
        price = 100.0 + index * slope
        rows.append(
            {
                "timestamp": index * 60,
                "open": price,
                "high": price + 0.02,
                "low": price - 0.02,
                "close": price + slope,
                "volume": 1.0,
            }
        )
    return rows


def test_build_timeframe_bars_drops_incomplete_bucket():
    bars = _bars(11)

    result = build_timeframe_bars(bars, "10m", now_ts=11 * 60)

    assert [item["timestamp"] for item in result] == [0]
    assert result[0]["bar_count"] == 10


def test_snapshot_contains_requested_periods_and_completed_bars():
    result = build_multi_timeframe_snapshot(_bars(8 * 60), now_ts=8 * 60 * 60)

    assert list(result["timeframes"]) == ["4h", "30m", "15m", "10m", "5m"]
    assert result["timeframes"]["4h"]["bar_count"] == 2
    assert result["timeframes"]["30m"]["bar_count"] == 16
    assert result["timeframes"]["15m"]["bar_count"] == 32
    assert result["timeframes"]["10m"]["bar_count"] == 48
    assert result["timeframes"]["5m"]["bar_count"] == 96
    assert result["aligned_direction"] == "long"
    assert "ema_fast" in result["timeframes"]["5m"]
    assert "ema_slow" in result["timeframes"]["5m"]
    assert "rsi" in result["timeframes"]["5m"]
    assert "atr_pct" in result["timeframes"]["5m"]


def test_snapshot_fails_closed_when_high_timeframe_directions_conflict():
    bars = _bars(8 * 60)
    # The final 4h bucket falls while the lower timeframes turn down. The
    # snapshot must not manufacture a long decision from the older trend.
    for index, row in enumerate(bars[7 * 60 :], start=7 * 60):
        price = 102.5 + (479 - index) * 0.03
        row["open"] = price
        row["high"] = price + 0.02
        row["low"] = price - 0.02
        row["close"] = price - 0.02

    result = build_multi_timeframe_snapshot(bars, now_ts=8 * 60 * 60)

    assert result["aligned_direction"] == "hold"
    assert result["conflict"] is True


def test_snapshot_reports_insufficient_history_instead_of_guessing():
    result = build_multi_timeframe_snapshot(_bars(60), now_ts=60 * 60)

    assert result["timeframes"]["4h"]["direction"] == "hold"
    assert result["timeframes"]["4h"]["status"] == "insufficient_history"
    assert result["aligned_direction"] == "hold"
