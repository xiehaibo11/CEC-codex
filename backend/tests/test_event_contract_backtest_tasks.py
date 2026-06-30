from datetime import datetime, timezone

import pytest

from services.event_contract.constants import EVENT_AI_NAMES
from services.event_contract_service import EventContractService


def _cfg(**overrides):
    base = {
        "symbol": "BTC",
        "exchange": "binance",
        "environment": "mainnet",
        "period": "1m",
        "expiry_minutes": 5,
        "consensus_mode": "rule_only",
        "consensus_threshold": 30,
        "start_time": "2026-06-29T00:20:00+00:00",
        "end_time": "2026-06-29T00:25:00+00:00",
        "enable_fake_breakout_filter": True,
        "enable_trap_filter": True,
        "enable_range_filter": True,
        "enable_multi_timeframe_filter": True,
        "enable_volume_filter": True,
        "enable_cvd_filter": False,
        "enable_l2_features": False,
        "enable_coinglass_features": False,
        "strict_data_quality": False,
        "warmup_bars": 5,
        "max_bars": 50,
    }
    base.update(overrides)
    return base


def _klines(count=40):
    start_ts = int(datetime(2026, 6, 29, 0, 0, tzinfo=timezone.utc).timestamp())
    return [
        {
            "timestamp": start_ts + idx * 60,
            "datetime": datetime.fromtimestamp(start_ts + idx * 60, tz=timezone.utc).isoformat(),
            "open": 100 + idx,
            "high": 101 + idx,
            "low": 99 + idx,
            "close": 100 + idx,
            "volume": 1000,
        }
        for idx in range(count)
    ]


def _patch_fast_backtest(monkeypatch, service):
    monkeypatch.setattr(service, "_load_klines", lambda *args, **kwargs: _klines())
    monkeypatch.setattr(service, "_audit_kline_series", lambda *args, **kwargs: {"warnings": [], "coverage_pct": 100})
    monkeypatch.setattr(service, "_validate_data_quality", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_load_coinglass_feature_bundle", lambda *args, **kwargs: {"enabled": False, "audit": {"enabled": False, "warnings": []}})
    monkeypatch.setattr(service, "_load_l2_feature_bundle", lambda *args, **kwargs: {"enabled": False, "audit": {"enabled": False, "warnings": []}})
    monkeypatch.setattr(
        service,
        "_analyze_snapshot",
        lambda history, cfg, **kwargs: {
            "allow_trade": False,
            "fake_breakout_risk": 0,
            "trap_risk": 0,
            "blocked_reasons": ["test hold"],
            "final_direction": "hold",
            "ai_participated": True,
            "ai_decisions": [],
            "factors": [],
            "ai_consensus": {
                "consensus_rate": 0,
                "consensus_source": "system_30_ai",
                "long_votes": 0,
                "short_votes": 0,
                "hold_votes": 30,
            },
            "event_signal": {"signal_type": "HOLD"},
            "signal_strength": 0,
            "market_state": "range",
            "reason_summary": "test hold",
        },
    )
    monkeypatch.setattr(service, "_persist_backtest", lambda *args, **kwargs: 99)


def test_backtest_loop_reports_progress_and_honors_pause(monkeypatch):
    from services.event_contract.tasks import EventBacktestPaused

    service = EventContractService()
    _patch_fast_backtest(monkeypatch, service)
    progress_events = []

    def progress_callback(event):
        progress_events.append(event)

    def pause_checker():
        return any(event.get("processed_decision_bars", 0) >= 1 for event in progress_events)

    with pytest.raises(EventBacktestPaused):
        service.run_backtest(
            object(),
            _cfg(),
            progress_callback=progress_callback,
            pause_checker=pause_checker,
        )

    assert any(event.get("phase") == "loading_data" for event in progress_events)
    assert any(event.get("processed_decision_bars", 0) >= 1 for event in progress_events)


def test_ai_review_status_builder_tracks_all_thirty_reviewers():
    from services.event_contract.tasks import build_ai_reviewer_statuses

    statuses = build_ai_reviewer_statuses(
        [
            {"ai_name": EVENT_AI_NAMES[0], "direction": "long", "confidence": 95},
            {"ai_name": EVENT_AI_NAMES[1], "direction": "hold", "confidence": 40},
        ]
    )

    assert len(statuses) == 30
    assert statuses[0]["status"] == "completed"
    assert statuses[0]["direction"] == "long"
    assert statuses[1]["status"] == "completed"
    assert statuses[2]["status"] == "pending"


def test_progress_algorithm_is_configurable_not_hardcoded():
    from services.event_contract.tasks import compute_progress

    progress = compute_progress(
        data_ready=True,
        processed_decision_bars=50,
        total_decision_bars=100,
        completed_ai_reviews=15,
        expected_ai_reviews=30,
        weights={"data": 0.2, "bars": 0.6, "ai": 0.2},
    )

    assert progress == 60.0
