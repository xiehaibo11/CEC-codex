"""TDD coverage for the rolling out-of-sample validation cycle (spec module 4):
automated frozen-parameter holdout windows + cumulative significance, so
nobody has to manually click the holdout endpoint anymore."""
from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import (
    EventContractBacktestRun,
    EventContractBacktestTask,
    EventContractPaperTrader,
    EventContractValidationLog,
)
from services.event_contract.backtest_stats import binomial_p_value, wilson_interval
import services.event_contract.rolling_validation as rolling_validation
from services.event_contract.rolling_validation import (
    END_LAG_SECONDS,
    cumulative_validation_stats,
    run_rolling_validation_cycle,
)

NOW = datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc)
NOW_TS = int(NOW.timestamp())


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            EventContractPaperTrader.__table__,
            EventContractValidationLog.__table__,
            EventContractBacktestRun.__table__,
            EventContractBacktestTask.__table__,
        ],
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _make_trader(db, fingerprint, enabled=True, name=None):
    trader = EventContractPaperTrader(
        name=name or f"trader-{fingerprint}",
        enabled=enabled,
        symbol="BTC",
        exchange="binance",
        environment="mainnet",
        config="{}",
        stake_amount=100.0,
        initial_balance=10000.0,
        current_balance=10000.0,
        strategy_fingerprint=fingerprint,
    )
    db.add(trader)
    db.commit()
    db.refresh(trader)
    return trader


def _make_backtest_run(db, fingerprint, end_time, config=None, wins=0, losses=0, status="completed"):
    config = config or {"symbol": "BTC", "exchange": "binance", "environment": "mainnet", "period": "1m"}
    summary = {"strategy_fingerprint": fingerprint, "wins": wins, "losses": losses}
    run = EventContractBacktestRun(
        symbol="BTC",
        exchange="binance",
        environment="mainnet",
        period="1m",
        start_time=_naive(end_time - timedelta(days=1)),
        end_time=_naive(end_time),
        config=json.dumps(config),
        summary=json.dumps(summary),
        status=status,
        total_trades=wins + losses,
        win_rate=0,
        final_equity=10000.0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _make_task(db, task_id, status, run_id=None):
    task = EventContractBacktestTask(
        id=task_id,
        status=status,
        symbol="BTC",
        run_id=run_id,
    )
    db.add(task)
    db.commit()
    return task


def _make_validation_log(db, fingerprint, **overrides):
    defaults = dict(
        strategy_fingerprint=fingerprint,
        status="recorded",
        decided=0,
        wins=0,
    )
    defaults.update(overrides)
    row = EventContractValidationLog(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# migration registration
# ---------------------------------------------------------------------------


def test_validation_log_migration_registered_last():
    migration_manager = importlib.import_module("database.migration_manager")
    migrations = migration_manager.MIGRATIONS
    assert "add_event_contract_validation_log.py" in migrations
    # Later feature migrations may append after it, but the validation-log
    # migration must still be registered before migrations that depend on the
    # event-contract validation record existing.
    if "add_ai_review_tables.py" in migrations:
        assert migrations.index("add_event_contract_validation_log.py") < migrations.index("add_ai_review_tables.py")


def test_validation_log_migration_upgrade_is_idempotent():
    """upgrade() must be safe to run repeatedly against the live dev postgres."""
    migration = importlib.import_module("database.migrations.add_event_contract_validation_log")
    migration.upgrade()
    migration.upgrade()


# ---------------------------------------------------------------------------
# (a) cumulative math over fake recorded segments
# ---------------------------------------------------------------------------


def test_cumulative_stats_aggregates_recorded_segments_wilson_math(session):
    fingerprint = "fp-cumulative-math"
    _make_backtest_run(
        session,
        fingerprint,
        end_time=NOW - timedelta(hours=48),
        config={"win_payout_ratio": 0.8, "fee_rate": 0.0},
    )
    # Two recorded segments summing to wins=30, decided=50 (wilson(30,50) check).
    _make_validation_log(
        session,
        fingerprint,
        window_start=_naive(NOW - timedelta(hours=36)),
        window_end=_naive(NOW - timedelta(hours=24)),
        decided=30,
        wins=20,
        status="recorded",
    )
    _make_validation_log(
        session,
        fingerprint,
        window_start=_naive(NOW - timedelta(hours=24)),
        window_end=_naive(NOW - timedelta(hours=12)),
        decided=20,
        wins=10,
        status="recorded",
    )
    # A still-pending segment must not be folded into the cumulative totals.
    _make_validation_log(
        session,
        fingerprint,
        window_start=_naive(NOW - timedelta(hours=12)),
        window_end=_naive(NOW),
        decided=0,
        wins=0,
        status="pending",
    )

    result = cumulative_validation_stats(session, fingerprint)

    assert result["n"] == 50
    assert result["wins"] == 30
    assert result["decided_win_rate"] == round(30 / 50 * 100, 2)
    expected_lo, expected_hi = wilson_interval(30, 50)
    assert result["ci_low"] == expected_lo
    assert result["ci_high"] == expected_hi
    break_even = (1 + 0.0) / (0.8 + 1) * 100
    assert result["break_even_win_rate"] == round(break_even, 2)
    assert result["p_value"] == round(binomial_p_value(30, 50, break_even / 100), 6)
    assert result["target_n"] == 550
    assert len(result["segments"]) == 3
    assert result["fingerprint"] == fingerprint


def test_cumulative_stats_zero_decided_is_honest_zeros(session):
    fingerprint = "fp-no-data-yet"

    result = cumulative_validation_stats(session, fingerprint)

    assert result["n"] == 0
    assert result["wins"] == 0
    assert result["decided_win_rate"] == 0.0
    assert result["ci_low"] == 0.0
    assert result["ci_high"] == 0.0
    assert result["p_value"] == 1.0
    assert result["segments"] == []


# ---------------------------------------------------------------------------
# (b) launch phase
# ---------------------------------------------------------------------------


def test_launch_phase_creates_pending_log_and_task_when_window_elapsed(session, monkeypatch):
    fingerprint = "fp-launch-due"
    _make_trader(session, fingerprint)
    source_run = _make_backtest_run(
        session,
        fingerprint,
        end_time=NOW - timedelta(hours=20),  # last_end 20h ago, well past the 12h cycle
        config={"symbol": "BTC", "exchange": "binance", "environment": "mainnet", "period": "1m"},
    )

    created_calls = []
    started_calls = []

    def fake_create(db, *, config, user_id=None, name=None):
        created_calls.append(config)
        return {"task_id": 4242}

    def fake_start(task_id):
        started_calls.append(task_id)

    monkeypatch.setattr(rolling_validation, "create_event_backtest_task", fake_create)
    monkeypatch.setattr(rolling_validation, "start_event_backtest_task_thread", fake_start)

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["launched"] == 1
    assert counters["recorded"] == 0
    assert len(created_calls) == 1
    assert started_calls == [4242]

    # The replayed config carries the frozen strategy params plus the new window.
    replayed = created_calls[0]
    assert replayed["symbol"] == "BTC"
    expected_start = source_run.end_time.replace(tzinfo=timezone.utc)
    expected_end_ts = NOW_TS - END_LAG_SECONDS
    assert replayed["start_time"] == expected_start.isoformat()
    assert replayed["end_time"] == datetime.fromtimestamp(expected_end_ts, tz=timezone.utc).isoformat()

    logs = session.query(EventContractValidationLog).filter_by(strategy_fingerprint=fingerprint).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.status == "pending"
    assert log.task_id == 4242
    assert log.source_run_id == source_run.id
    assert log.window_start == source_run.end_time
    assert log.window_end == _naive(datetime.fromtimestamp(expected_end_ts, tz=timezone.utc))


def test_launch_phase_skips_fingerprint_whose_window_has_not_elapsed(session, monkeypatch):
    fingerprint = "fp-launch-fresh"
    _make_trader(session, fingerprint)
    _make_backtest_run(
        session,
        fingerprint,
        end_time=NOW - timedelta(hours=1),  # only 1h ago - well under the 12h cycle
    )

    created_calls = []
    monkeypatch.setattr(
        rolling_validation,
        "create_event_backtest_task",
        lambda db, **kw: created_calls.append(kw) or {"task_id": 1},
    )
    monkeypatch.setattr(rolling_validation, "start_event_backtest_task_thread", lambda task_id: None)

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["launched"] == 0
    assert created_calls == []
    logs = session.query(EventContractValidationLog).filter_by(strategy_fingerprint=fingerprint).all()
    assert logs == []


def test_launch_phase_resumes_from_latest_validation_log_window_end(session, monkeypatch):
    fingerprint = "fp-launch-resume"
    _make_trader(session, fingerprint)
    _make_backtest_run(session, fingerprint, end_time=NOW - timedelta(days=5))
    # A prior validated window ended only 1h ago -> should NOT launch, even
    # though the original source run's end_time was long ago.
    _make_validation_log(
        session,
        fingerprint,
        window_start=_naive(NOW - timedelta(hours=13)),
        window_end=_naive(NOW - timedelta(hours=1)),
        decided=10,
        wins=6,
        status="recorded",
    )

    monkeypatch.setattr(
        rolling_validation, "create_event_backtest_task", lambda db, **kw: pytest.fail("must not launch")
    )
    monkeypatch.setattr(rolling_validation, "start_event_backtest_task_thread", lambda task_id: None)

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["launched"] == 0


def test_launch_phase_guards_against_duplicate_pending_launch(session, monkeypatch):
    """Pending row still unresolved and older than 12h → launch phase does
    NOT create a new task/log row."""
    fingerprint = "fp-launch-duplicate-guard"
    _make_trader(session, fingerprint)
    _make_backtest_run(
        session,
        fingerprint,
        end_time=NOW - timedelta(hours=20),  # source run ended 20h ago
    )
    # A pending validation log with old window_end (>12h ago, so a new window
    # WOULD normally be due). But since status='pending', we must NOT launch.
    _make_validation_log(
        session,
        fingerprint,
        window_start=_naive(NOW - timedelta(hours=24)),
        window_end=_naive(NOW - timedelta(hours=14)),  # ended 14h ago, past 12h threshold
        status="pending",
        task_id=None,  # or could be set to some task_id
    )

    created_calls = []
    started_calls = []

    def fake_create(db, *, config, user_id=None, name=None):
        created_calls.append(config)
        return {"task_id": 9999}

    def fake_start(task_id):
        started_calls.append(task_id)

    monkeypatch.setattr(rolling_validation, "create_event_backtest_task", fake_create)
    monkeypatch.setattr(rolling_validation, "start_event_backtest_task_thread", fake_start)

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    # Must NOT launch a new task
    assert counters["launched"] == 0
    assert created_calls == []
    assert started_calls == []

    # Still exactly one log row for this fingerprint, unchanged
    logs = session.query(EventContractValidationLog).filter_by(strategy_fingerprint=fingerprint).all()
    assert len(logs) == 1
    assert logs[0].status == "pending"
    assert logs[0].task_id is None


# ---------------------------------------------------------------------------
# (c) record phase
# ---------------------------------------------------------------------------


def test_record_phase_transitions_pending_to_recorded_on_task_completion(session):
    fingerprint = "fp-record-me"
    run = _make_backtest_run(session, fingerprint, end_time=NOW - timedelta(hours=1), wins=7, losses=3)
    _make_task(session, task_id=999, status="completed", run_id=run.id)
    log = _make_validation_log(
        session,
        fingerprint,
        status="pending",
        task_id=999,
        window_start=_naive(NOW - timedelta(hours=13)),
        window_end=_naive(NOW - timedelta(hours=1)),
    )

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["recorded"] == 1
    session.refresh(log)
    assert log.status == "recorded"
    assert log.decided == 10
    assert log.wins == 7
    assert log.holdout_run_id == run.id


def test_record_phase_marks_failed_task_as_failed(session):
    fingerprint = "fp-record-fail"
    _make_task(session, task_id=1000, status="failed", run_id=None)
    log = _make_validation_log(
        session,
        fingerprint,
        status="pending",
        task_id=1000,
    )

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["recorded"] == 0
    session.refresh(log)
    assert log.status == "failed"


def test_record_phase_leaves_still_running_task_pending(session):
    fingerprint = "fp-record-running"
    _make_task(session, task_id=1001, status="running", run_id=None)
    log = _make_validation_log(
        session,
        fingerprint,
        status="pending",
        task_id=1001,
    )

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["recorded"] == 0
    session.refresh(log)
    assert log.status == "pending"


# ---------------------------------------------------------------------------
# (d) per-fingerprint exception isolation
# ---------------------------------------------------------------------------


def test_launch_phase_isolates_exception_per_fingerprint(session, monkeypatch):
    broken_fp = "fp-broken-launch"
    healthy_fp = "fp-healthy-launch"
    _make_trader(session, broken_fp)
    _make_trader(session, healthy_fp)
    _make_backtest_run(
        session, broken_fp, end_time=NOW - timedelta(hours=20), config={"_boom": True, "symbol": "BTC"}
    )
    _make_backtest_run(session, healthy_fp, end_time=NOW - timedelta(hours=20), config={"symbol": "BTC"})

    def fake_create(db, *, config, user_id=None, name=None):
        if config.get("_boom"):
            raise RuntimeError("boom")
        return {"task_id": 555}

    monkeypatch.setattr(rolling_validation, "create_event_backtest_task", fake_create)
    monkeypatch.setattr(rolling_validation, "start_event_backtest_task_thread", lambda task_id: None)

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["launched"] == 1
    broken_logs = session.query(EventContractValidationLog).filter_by(strategy_fingerprint=broken_fp).all()
    healthy_logs = session.query(EventContractValidationLog).filter_by(strategy_fingerprint=healthy_fp).all()
    assert broken_logs == []
    assert len(healthy_logs) == 1
    assert healthy_logs[0].task_id == 555


def test_record_phase_isolates_exception_per_row(session, monkeypatch):
    ok_fp = "fp-record-ok"
    broken_fp = "fp-record-broken"
    ok_run = _make_backtest_run(session, ok_fp, end_time=NOW - timedelta(hours=1), wins=2, losses=1)
    _make_task(session, task_id=2000, status="completed", run_id=ok_run.id)
    ok_log = _make_validation_log(session, ok_fp, status="pending", task_id=2000)
    # task_id=2001's row processing blows up with an unexpected (non-ValueError)
    # exception - this must not stop the ok row from being recorded, and must
    # not corrupt the broken row's persisted state (left untouched, not "failed").
    _make_task(session, task_id=2001, status="completed", run_id=ok_run.id)
    broken_log = _make_validation_log(session, broken_fp, status="pending", task_id=2001)

    real_get_task = rolling_validation.get_event_backtest_task

    def flaky_get_task(db, task_id):
        if task_id == 2001:
            raise RuntimeError("boom")
        return real_get_task(db, task_id)

    monkeypatch.setattr(rolling_validation, "get_event_backtest_task", flaky_get_task)

    counters = run_rolling_validation_cycle(now_ts=NOW_TS, db=session)

    assert counters["recorded"] == 1
    session.refresh(ok_log)
    session.refresh(broken_log)
    assert ok_log.status == "recorded"
    assert ok_log.decided == 3
    assert ok_log.wins == 2
    # Untouched - the exception was rolled back before any status write landed.
    assert broken_log.status == "pending"
