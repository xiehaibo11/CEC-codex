"""Strike must come from the first observable bar OPEN at/after the decision."""
from datetime import datetime, timezone

from services.event_contract_service import EventContractService, event_contract_service


def _klines(start=1000, interval=60, count=10, open_base=100.0):
    return [
        {"timestamp": start + i * interval, "open": open_base + i, "high": 0, "low": 0,
         "close": open_base + i + 0.5, "volume": 1.0}
        for i in range(count)
    ]


def test_entry_bar_is_bar_opening_at_decision_ts():
    klines = _klines()
    # decision at close of bar 0 => decision_ts = 1060 = open ts of bar 1
    idx, lag = event_contract_service._resolve_entry_bar(klines, 1060, 3, 60, 60)
    assert idx == 1
    assert lag == 0
    assert klines[idx]["open"] == 101.0


def test_delay_longer_than_bar_advances_entry():
    klines = _klines()
    # delay 61s pushes target into bar 2 [1120, 1180)
    idx, _ = event_contract_service._resolve_entry_bar(klines, 1060, 61, 60, 120)
    assert idx == 2


def test_gap_exceeding_lag_tolerance_returns_none():
    klines = _klines()[:2] + _klines(start=1600, count=3)  # gap after bar 1
    idx, lag = event_contract_service._resolve_entry_bar(klines, 1120, 3, 60, 60)
    assert idx is None
    assert lag > 60


def test_delay_beyond_last_bar_returns_none_with_positive_lag():
    """Regression for end-of-data truncation: target_ts lands past the last bar's
    close, but the walk loop stops at len(klines)-1 and must not silently accept
    that bar as the strike. A large lag tolerance isolates this from the
    lag-vs-decision_ts tolerance check."""
    klines = [{"timestamp": 0}, {"timestamp": 60}]
    idx, lag = event_contract_service._resolve_entry_bar(klines, 60, 170, 60, 1000)
    assert idx is None
    assert lag > 0
    assert lag == 170


def _long_allow_trade_analysis():
    return {
        "allow_trade": True,
        "fake_breakout_risk": 0,
        "trap_risk": 0,
        "blocked_reasons": [],
        "final_direction": "long",
        "ai_participated": True,
        "ai_decisions": [],
        "factors": [],
        "ai_consensus": {
            "consensus_rate": 100,
            "consensus_source": "system_panel",
            "long_votes": 30,
            "short_votes": 0,
            "hold_votes": 0,
        },
        "event_signal": {"signal_type": "LONG_BREAKOUT"},
        "signal_strength": 80,
        "market_state": "trend",
        "reason_summary": "test long",
    }


def test_backtest_trade_prices_are_strike_and_expiry_bar_opens(monkeypatch):
    """End-to-end: with every bar having open != close, the resulting trade must
    price off the strike (entry) bar's OPEN and the expiry bar's OPEN, not any
    close, and entry_time must be the strike bar's open timestamp."""
    base_ts = 1_700_000_000
    interval = 60
    klines = _klines(start=base_ts, interval=interval, count=40)

    service = EventContractService()
    monkeypatch.setattr(service, "_load_klines", lambda *args, **kwargs: klines)
    monkeypatch.setattr(service, "_sanitize_klines", lambda kls: (kls, {"input_bars": len(kls), "output_bars": len(kls), "dropped_invalid_bars": 0, "dropped_duplicate_bars": 0, "extreme_move_bars": 0, "max_abs_move_pct": 0.0, "warnings": []}))
    monkeypatch.setattr(service, "_audit_kline_series", lambda *args, **kwargs: {"warnings": [], "coverage_pct": 100})
    monkeypatch.setattr(service, "_validate_data_quality", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        service,
        "_load_coinglass_feature_bundle",
        lambda *args, **kwargs: {"enabled": False, "audit": {"enabled": False, "warnings": []}},
    )
    monkeypatch.setattr(
        service,
        "_load_l2_feature_bundle",
        lambda *args, **kwargs: {"enabled": False, "audit": {"enabled": False, "warnings": []}},
    )
    monkeypatch.setattr(service, "_load_flow_feature_bundle", lambda *args, **kwargs: {"enabled": False, "warnings": []})
    monkeypatch.setattr(service, "_analyze_snapshot", lambda history, cfg, **kwargs: _long_allow_trade_analysis())
    monkeypatch.setattr(service, "_persist_backtest", lambda *args, **kwargs: 1)

    warmup_bars = 5
    # decision_ts for klines[warmup_bars] = its timestamp + interval; narrow the
    # window to exactly that instant so only a single decision bar fires.
    decision_ts = klines[warmup_bars]["timestamp"] + interval
    start_iso = datetime.fromtimestamp(decision_ts, tz=timezone.utc).isoformat()
    end_iso = datetime.fromtimestamp(decision_ts + 1, tz=timezone.utc).isoformat()

    cfg = {
        "symbol": "BTC",
        "exchange": "binance",
        "environment": "mainnet",
        "period": "1m",
        "expiry_minutes": 5,
        "consensus_mode": "rule_only",
        "delay_seconds": 0,
        "warmup_bars": warmup_bars,
        "max_bars": 50,
        "start_time": start_iso,
        "end_time": end_iso,
    }

    result = service.run_backtest(object(), cfg)

    assert len(result["trades"]) == 1
    trade = result["trades"][0]

    entry_idx = warmup_bars + 1  # decision_ts == klines[warmup_bars + 1]["timestamp"]
    expiry_idx = entry_idx + 5  # expiry_minutes=5 on a 1m period => +5 bars

    assert klines[entry_idx]["open"] != klines[entry_idx]["close"]
    assert klines[expiry_idx]["open"] != klines[expiry_idx]["close"]

    # Entry price = strike bar OPEN + cost-floor slippage (min 2bps + 1bp impact).
    # Expiry price = raw expiry bar OPEN with no slippage applied.
    assert abs(trade["entry_price"] - klines[entry_idx]["open"]) < 0.05
    assert trade["entry_price"] != klines[entry_idx]["close"]
    assert trade["expiry_price"] == klines[expiry_idx]["open"]
    assert trade["entry_time"] == (
        datetime.fromtimestamp(klines[entry_idx]["timestamp"], tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    assert result["equity_curve"][-1]["timestamp"] == klines[expiry_idx]["timestamp"] * 1000


def _stub_service_for_multi_trade(monkeypatch, klines):
    """Same stubbing pattern as test_backtest_trade_prices_are_strike_and_expiry_bar_opens,
    factored out so multiple decision bars can be exercised across trade constraints."""
    service = EventContractService()
    monkeypatch.setattr(service, "_load_klines", lambda *args, **kwargs: klines)
    monkeypatch.setattr(service, "_sanitize_klines", lambda kls: (kls, {"input_bars": len(kls), "output_bars": len(kls), "dropped_invalid_bars": 0, "dropped_duplicate_bars": 0, "extreme_move_bars": 0, "max_abs_move_pct": 0.0, "warnings": []}))
    monkeypatch.setattr(service, "_audit_kline_series", lambda *args, **kwargs: {"warnings": [], "coverage_pct": 100})
    monkeypatch.setattr(service, "_validate_data_quality", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        service,
        "_load_coinglass_feature_bundle",
        lambda *args, **kwargs: {"enabled": False, "audit": {"enabled": False, "warnings": []}},
    )
    monkeypatch.setattr(
        service,
        "_load_l2_feature_bundle",
        lambda *args, **kwargs: {"enabled": False, "audit": {"enabled": False, "warnings": []}},
    )
    monkeypatch.setattr(service, "_load_flow_feature_bundle", lambda *args, **kwargs: {"enabled": False, "warnings": []})
    monkeypatch.setattr(service, "_analyze_snapshot", lambda history, cfg, **kwargs: _long_allow_trade_analysis())
    monkeypatch.setattr(service, "_persist_backtest", lambda *args, **kwargs: 1)
    return service


def _multi_trade_cfg(klines, *, warmup_bars, decision_bars, interval, **overrides):
    # Window covers exactly `decision_bars` decision instants, one per bar from
    # klines[warmup_bars] through klines[warmup_bars + decision_bars - 1].
    decision_ts_start = klines[warmup_bars]["timestamp"] + interval
    decision_ts_end = klines[warmup_bars + decision_bars - 1]["timestamp"] + interval
    cfg = {
        "symbol": "BTC",
        "exchange": "binance",
        "environment": "mainnet",
        "period": "1m",
        "expiry_minutes": 5,
        "consensus_mode": "rule_only",
        "delay_seconds": 0,
        "warmup_bars": warmup_bars,
        "max_bars": 50,
        "start_time": datetime.fromtimestamp(decision_ts_start, tz=timezone.utc).isoformat(),
        "end_time": datetime.fromtimestamp(decision_ts_end, tz=timezone.utc).isoformat(),
    }
    cfg.update(overrides)
    return cfg


def test_backtest_non_overlapping_only_spaces_trades_past_expiry(monkeypatch):
    """Multi-trade coverage for the overlap constraint: with 10 decision bars (1m
    period, 5m expiry) and every bar allowed long, non_overlapping_only=True must
    skip decision bars whose entry would fire before the prior trade's expiry, and
    every trade actually taken must start at/after the previous trade's expiry."""
    base_ts = 1_700_000_000
    interval = 60
    klines = _klines(start=base_ts, interval=interval, count=40)
    service = _stub_service_for_multi_trade(monkeypatch, klines)

    cfg = _multi_trade_cfg(
        klines, warmup_bars=5, decision_bars=10, interval=interval, non_overlapping_only=True
    )
    result = service.run_backtest(object(), cfg)

    assert result["summary"]["overlap_skipped_count"] > 0
    trades = result["trades"]
    assert len(trades) >= 2
    for prev_trade, next_trade in zip(trades, trades[1:]):
        assert next_trade["entry_time"] >= prev_trade["expiry_time"]


def test_backtest_overlap_disabled_produces_more_trades(monkeypatch):
    """Same 10-bar window as the non-overlapping test above, but with
    non_overlapping_only=False every allowed decision bar should convert into a
    trade, so strictly more trades are produced than the constrained run."""
    base_ts = 1_700_000_000
    interval = 60
    klines = _klines(start=base_ts, interval=interval, count=40)

    overlap_service = _stub_service_for_multi_trade(monkeypatch, klines)
    overlap_cfg = _multi_trade_cfg(
        klines, warmup_bars=5, decision_bars=10, interval=interval, non_overlapping_only=True
    )
    overlap_result = overlap_service.run_backtest(object(), overlap_cfg)

    no_overlap_service = _stub_service_for_multi_trade(monkeypatch, klines)
    no_overlap_cfg = _multi_trade_cfg(
        klines, warmup_bars=5, decision_bars=10, interval=interval, non_overlapping_only=False
    )
    no_overlap_result = no_overlap_service.run_backtest(object(), no_overlap_cfg)

    assert len(no_overlap_result["trades"]) > len(overlap_result["trades"])
