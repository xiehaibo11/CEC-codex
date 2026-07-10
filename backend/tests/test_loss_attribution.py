"""Six-dimension loss attribution + counterfactual replay (问题.md §3).

Losing trades are the strategy's best training data, but only with structured
attribution: every settled loss gets tagged on six dimensions (signal quality,
regime mismatch, execution, position sizing, trade management, event shock),
counterfactuals are replayed against real klines ("what if no stop / half
size / 2x wider stop"), and commonalities across losses become explicit rule
patch suggestions instead of vibes.
"""
from __future__ import annotations

import pytest

from services.loss_attribution import aggregate_attribution, analyze_loss

ENTRY_TS = 1_780_000_000  # arbitrary aligned epoch


def _bar(ts, price, high=None, low=None):
    return {
        "timestamp": ts,
        "open": price,
        "high": high if high is not None else price + 0.05,
        "low": low if low is not None else price - 0.05,
        "close": price,
    }


def _klines_short_stopped_then_recovers():
    """4h uptrend into entry at 100; spikes to 101.6 (sweeping a 1% stop),
    then falls to 98.5 by +4h - the 2026-07-06 shape: counter-trend short,
    stop swept, thesis eventually right."""
    bars = []
    for i in range(240):  # 4h before entry: 99 -> 100 uptrend
        ts = ENTRY_TS - (240 - i) * 60
        bars.append(_bar(ts, 99.0 + i / 240.0))
    for i in range(60):  # first hour after entry: rally to 101.6
        bars.append(_bar(ENTRY_TS + i * 60, 100.0 + 1.6 * i / 59.0))
    for i in range(180):  # next 3h: fall to 98.5
        bars.append(_bar(ENTRY_TS + (60 + i) * 60, 101.6 - 3.1 * i / 179.0))
    return bars


def _decision(**overrides):
    decision = {
        "decision_id": 396,
        "symbol": "BTC",
        "operation": "sell",
        "entry_price": 100.0,
        "entry_ts": ENTRY_TS,
        "realized_pnl": -16.75,
        "reason": "BTC dips below $63k amid ETF outflows and geopolitical risks",
        "stop_loss_price": 101.0,
        "take_profit_price": 97.0,
        "leverage": 1,
        "target_portion": 0.2,
        "prev_portion": 0.0,
        "signal_trigger_id": None,
    }
    decision.update(overrides)
    return decision


class TestSixDimensions:
    def test_counter_trend_short_tagged(self):
        row = analyze_loss(_decision(), _klines_short_stopped_then_recovers())
        assert "counter_trend_short" in row["tags"]

    def test_news_narrative_tagged_for_non_signal_decision(self):
        row = analyze_loss(_decision(), _klines_short_stopped_then_recovers())
        assert "news_narrative_driven" in row["tags"]

    def test_signal_decision_not_tagged_as_narrative(self):
        row = analyze_loss(
            _decision(signal_trigger_id=7, reason="DEPTH_RATIO triggered at 8.5"),
            _klines_short_stopped_then_recovers(),
        )
        assert "news_narrative_driven" not in row["tags"]

    def test_stop_within_noise_tagged(self):
        # 1% stop vs prior-hour range ~0.35 plus wick noise: craft a wide
        # pre-entry hour so the 1% stop sits INSIDE typical hourly range.
        bars = _klines_short_stopped_then_recovers()
        for bar in bars[180:240]:  # last pre-entry hour: widen to ±1.2
            bar["high"] = bar["close"] + 1.2
            bar["low"] = bar["close"] - 1.2
        row = analyze_loss(_decision(), bars)
        assert "stop_within_1h_noise" in row["tags"]

    def test_stacking_add_tagged(self):
        row = analyze_loss(
            _decision(prev_portion=0.8), _klines_short_stopped_then_recovers()
        )
        assert "stacking_add" in row["tags"]

    def test_oversized_and_leverage_tags(self):
        # 0.5 is the sanctioned default sizing (2026-07-10); the tag fires
        # only ABOVE it.
        row = analyze_loss(
            _decision(target_portion=0.8, leverage=10),
            _klines_short_stopped_then_recovers(),
        )
        assert "oversized_portion" in row["tags"]
        assert "high_leverage" in row["tags"]

    def test_sanctioned_default_portion_not_tagged(self):
        row = analyze_loss(
            _decision(target_portion=0.5, leverage=3),
            _klines_short_stopped_then_recovers(),
        )
        assert "oversized_portion" not in row["tags"]


class TestCounterfactuals:
    def test_no_stop_replay_shows_recovery(self):
        row = analyze_loss(_decision(), _klines_short_stopped_then_recovers())
        cf = row["counterfactuals"]
        # Short from 100: at +4h price ~98.5 -> ~+1.5% without the stop.
        assert cf["no_stop_pnl_pct_4h"] == pytest.approx(1.5, abs=0.3)
        # First hour rallies to 101.6 -> the 1% stop was indeed hit.
        assert cf["stop_was_hit"] is True

    def test_wider_stop_survives_the_sweep(self):
        row = analyze_loss(_decision(), _klines_short_stopped_then_recovers())
        cf = row["counterfactuals"]
        # 2x stop = 102: the 101.6 spike does not reach it -> position
        # survives and ends near the +4h price.
        assert cf["double_stop_pnl_pct"] > 0

    def test_half_size_halves_the_loss(self):
        row = analyze_loss(_decision(realized_pnl=-30.0), _klines_short_stopped_then_recovers())
        assert row["counterfactuals"]["half_size_pnl"] == pytest.approx(-15.0)


class TestAggregate:
    def test_commonalities_and_rule_suggestions(self):
        rows = [
            {"tags": ["news_narrative_driven", "counter_trend_short"], "realized_pnl": -10},
            {"tags": ["news_narrative_driven", "stop_within_1h_noise"], "realized_pnl": -20},
            {"tags": ["news_narrative_driven"], "realized_pnl": -5},
            {"tags": ["oversized_portion"], "realized_pnl": -8},
        ]
        report = aggregate_attribution(rows)
        top = report["commonalities"][0]
        assert top["tag"] == "news_narrative_driven"
        assert top["share_pct"] == pytest.approx(75.0)
        # >=50% share tags must produce an actionable rule suggestion
        assert any("news_narrative_driven" in s["tag"] for s in report["rule_suggestions"])

    def test_empty_input(self):
        report = aggregate_attribution([])
        assert report["total_losses"] == 0
        assert report["rule_suggestions"] == []
