from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from services.event_contract.constants import EVENT_AI_NAMES, MAIN_LOGIC_REVIEWER_NAME
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
    monkeypatch.setattr(service, "_load_flow_feature_bundle", lambda *args, **kwargs: {"enabled": False, "warnings": []})
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
                "consensus_source": "system_panel",
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


def test_ai_review_status_builder_tracks_configured_25_vote_panel():
    from services.event_contract.tasks import build_ai_reviewer_statuses

    statuses = build_ai_reviewer_statuses(
        [
            {"ai_name": EVENT_AI_NAMES[0], "direction": "long", "confidence": 95},
            {"ai_name": EVENT_AI_NAMES[1], "direction": "hold", "confidence": 40},
        ]
    )

    assert len(statuses) == 25
    assert statuses[0]["ai_name"] == MAIN_LOGIC_REVIEWER_NAME
    assert statuses[0]["status"] == "pending"
    assert statuses[1]["status"] == "completed"
    assert statuses[1]["direction"] == "long"
    assert statuses[2]["status"] == "completed"
    assert statuses[3]["status"] == "pending"


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


def test_latest_backtest_task_is_scoped_to_current_user_or_anonymous():
    from services.event_contract.tasks import find_latest_event_backtest_task, get_latest_event_backtest_task

    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE event_contract_backtest_tasks (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NULL,
                run_id INTEGER NULL,
                name TEXT NULL,
                status TEXT,
                symbol TEXT,
                exchange TEXT,
                environment TEXT,
                period TEXT,
                config TEXT,
                progress_pct REAL,
                phase TEXT,
                processed_decision_bars INTEGER,
                total_decision_bars INTEGER,
                completed_ai_reviews INTEGER,
                expected_ai_reviews INTEGER,
                ai_reviewer_statuses TEXT,
                latest_message TEXT NULL,
                error_message TEXT NULL,
                started_at TEXT NULL,
                finished_at TEXT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        ))
        for task_id, user_id, created_at in [
            (1, None, "2026-07-01T00:00:00+00:00"),
            (2, 7, "2026-07-01T01:00:00+00:00"),
            (3, None, "2026-07-01T02:00:00+00:00"),
        ]:
            conn.execute(
                text(
                    """
                    INSERT INTO event_contract_backtest_tasks (
                        id, user_id, run_id, status, symbol, exchange, environment,
                        period, config, progress_pct, phase, processed_decision_bars,
                        total_decision_bars, completed_ai_reviews, expected_ai_reviews,
                        ai_reviewer_statuses, created_at, updated_at
                    ) VALUES (
                        :id, :user_id, :run_id, 'completed', 'BTC', 'binance', 'mainnet',
                        '1m', :config, 100, 'completed', 1, 1, 0, 0,
                        '[]', :created_at, :created_at
                    )
                    """
                ),
                {
                    "id": task_id,
                    "user_id": user_id,
                    "run_id": task_id + 40,
                    "config": json.dumps({"reviewer_panel_size": 25}),
                    "created_at": created_at,
                },
            )

    with session_factory() as db:
        assert find_latest_event_backtest_task(db, user_id=999) is None
        assert get_latest_event_backtest_task(db, user_id=None)["task_id"] == 3
        assert get_latest_event_backtest_task(db, user_id=7)["task_id"] == 2


def test_professional_task_creation_uses_rule_only_display_state():
    from services.event_contract.tasks import create_event_backtest_task

    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE event_contract_backtest_tasks (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NULL,
                run_id INTEGER NULL,
                name TEXT NULL,
                status TEXT,
                symbol TEXT,
                exchange TEXT,
                environment TEXT,
                period TEXT,
                config TEXT,
                progress_pct REAL,
                phase TEXT,
                processed_decision_bars INTEGER,
                total_decision_bars INTEGER,
                completed_ai_reviews INTEGER,
                expected_ai_reviews INTEGER,
                ai_reviewer_statuses TEXT,
                latest_message TEXT NULL,
                error_message TEXT NULL,
                started_at TEXT NULL,
                finished_at TEXT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        ))

    with session_factory() as db:
        task = create_event_backtest_task(
            db,
            config=_cfg(
                decision_policy="professional_v1",
                consensus_mode="ai_confirmed",
                max_ai_evaluations=20,
                reviewer_panel_size=25,
            ),
        )

    assert task["config"]["decision_policy"] == "professional_v1"
    assert task["config"]["consensus_mode"] == "rule_only"
    assert task["config"]["max_ai_evaluations"] == 1
    assert {item["status"] for item in task["ai_reviewer_statuses"]} == {"skipped"}


def test_stale_running_event_backtest_task_expires_on_read():
    from services.event_contract.tasks import get_event_backtest_task

    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE event_contract_backtest_tasks (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NULL,
                run_id INTEGER NULL,
                name TEXT NULL,
                status TEXT,
                symbol TEXT,
                exchange TEXT,
                environment TEXT,
                period TEXT,
                config TEXT,
                progress_pct REAL,
                phase TEXT,
                processed_decision_bars INTEGER,
                total_decision_bars INTEGER,
                completed_ai_reviews INTEGER,
                expected_ai_reviews INTEGER,
                ai_reviewer_statuses TEXT,
                latest_message TEXT NULL,
                error_message TEXT NULL,
                started_at TEXT NULL,
                finished_at TEXT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        ))
        conn.execute(
            text(
                """
                INSERT INTO event_contract_backtest_tasks (
                    id, user_id, run_id, status, symbol, exchange, environment,
                    period, config, progress_pct, phase, processed_decision_bars,
                    total_decision_bars, completed_ai_reviews, expected_ai_reviews,
                    ai_reviewer_statuses, latest_message, created_at, updated_at
                ) VALUES (
                    10, NULL, NULL, 'running', 'BTC', 'binance', 'mainnet',
                    '1m', :config, 48.49, 'ai_review', 676, 1441, 75, 500,
                    '[]', 'Running 25 consensus votes for candidate 4',
                    '2000-01-01 00:00:00', '2000-01-01 00:00:00'
                )
                """
            ),
            {"config": json.dumps({"consensus_mode": "ai_confirmed", "reviewer_panel_size": 25})},
        )

    with session_factory() as db:
        task = get_event_backtest_task(db, 10)

    assert task["status"] == "failed"
    assert task["phase"] == "expired"
    assert "过期" in task["latest_message"]
    assert "stale" in task["error_message"].lower()
    assert task["finished_at"]


def test_latest_event_backtest_task_expires_stale_running_before_returning():
    from services.event_contract.tasks import find_latest_event_backtest_task

    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE event_contract_backtest_tasks (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NULL,
                run_id INTEGER NULL,
                name TEXT NULL,
                status TEXT,
                symbol TEXT,
                exchange TEXT,
                environment TEXT,
                period TEXT,
                config TEXT,
                progress_pct REAL,
                phase TEXT,
                processed_decision_bars INTEGER,
                total_decision_bars INTEGER,
                completed_ai_reviews INTEGER,
                expected_ai_reviews INTEGER,
                ai_reviewer_statuses TEXT,
                latest_message TEXT NULL,
                error_message TEXT NULL,
                started_at TEXT NULL,
                finished_at TEXT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        ))
        conn.execute(
            text(
                """
                INSERT INTO event_contract_backtest_tasks (
                    id, user_id, run_id, status, symbol, exchange, environment,
                    period, config, progress_pct, phase, processed_decision_bars,
                    total_decision_bars, completed_ai_reviews, expected_ai_reviews,
                    ai_reviewer_statuses, latest_message, created_at, updated_at
                ) VALUES (
                    11, NULL, NULL, 'running', 'BTC', 'binance', 'mainnet',
                    '1m', :config, 48.49, 'ai_review', 676, 1441, 75, 500,
                    '[]', 'Running 25 consensus votes for candidate 4',
                    '2000-01-01 00:00:00', '2000-01-01 00:00:00'
                )
                """
            ),
            {"config": json.dumps({"consensus_mode": "ai_confirmed", "reviewer_panel_size": 25})},
        )

    with session_factory() as db:
        task = find_latest_event_backtest_task(db, user_id=None)

    assert task is not None
    assert task["task_id"] == 11
    assert task["status"] == "failed"
    assert task["phase"] == "expired"
