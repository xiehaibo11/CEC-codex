"""TDD coverage for the Tier-1 price-locked delayed-settlement arbitrage
OPPORTUNITY DETECTOR (MVP: detector + persistent opportunity log only).

Rolling hypothetical 5-minute event contracts on BTC: each minute opens a new
window (strike = that minute's open), a window "locks" once price has been
continuously on one side of the strike for >= max(100s, 1/3 of the period)
AND the live distance from strike clears the minimum, and at expiry the row is
settled in place so lock accuracy can be measured. No venue quotes are used
anywhere (the quote leg is a documented TODO).
"""
from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base
from database.models.arb import ArbOpportunityLog
from services.arb_opportunity_detector import (
    run_detector_cycle,
    summarize_opportunities,
)
from services.event_contract_service import event_contract_service

BASE_TS = int(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc).timestamp())


def _naive_utc(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[ArbOpportunityLog.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _bar(ts, open_price, close_price):
    return {
        "timestamp": ts,
        "open": open_price,
        "high": max(open_price, close_price) + 0.5,
        "low": min(open_price, close_price) - 0.5,
        "close": close_price,
        "volume": 10.0,
    }


def _patch_klines(monkeypatch, klines):
    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)


def _make_row(db, **overrides):
    defaults = dict(
        symbol="BTC",
        window_start=_naive_utc(BASE_TS),
        strike=100.0,
        direction="above",
        locked_at=_naive_utc(BASE_TS + 170),
        remaining_seconds=130,
        distance_pct=1.5,
        outcome="pending",
    )
    defaults.update(overrides)
    row = ArbOpportunityLog(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Lock detection: fires only when BOTH sustained-time and distance are met
# ---------------------------------------------------------------------------


def test_lock_fires_when_sustained_and_distance_both_satisfied(monkeypatch, session):
    # Window at BASE_TS: strike 100.0. Closes at +60 (101), +120 (101.2) and the
    # forming bar's live close 101.5 are all above strike -> continuous side
    # since the first observation at BASE_TS+60, i.e. 110s sustained at
    # now=BASE_TS+170 (>= 100s) with distance 1.5% (>= 0.05%).
    klines = [
        _bar(BASE_TS, 100.0, 101.0),
        _bar(BASE_TS + 60, 101.0, 101.2),
        _bar(BASE_TS + 120, 101.2, 101.5),  # forming at now
    ]
    now_ts = BASE_TS + 170
    _patch_klines(monkeypatch, klines)

    counters = run_detector_cycle(now_ts=now_ts, db=session)

    assert counters == {"locked": 1, "settled": 0, "errors": 0}
    rows = session.query(ArbOpportunityLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == "BTC"
    assert row.window_start == _naive_utc(BASE_TS)
    assert row.strike == 100.0
    assert row.direction == "above"
    assert row.locked_at == _naive_utc(now_ts)
    assert row.remaining_seconds == 130
    assert row.distance_pct == pytest.approx(1.5)
    assert row.outcome == "pending"
    assert row.final_price is None


def test_no_lock_when_distance_too_small(monkeypatch, session):
    # Same sustained-side structure, but live distance is only 0.04% < 0.05%.
    klines = [
        _bar(BASE_TS, 100.0, 100.02),
        _bar(BASE_TS + 60, 100.02, 100.03),
        _bar(BASE_TS + 120, 100.03, 100.04),
    ]
    now_ts = BASE_TS + 170
    _patch_klines(monkeypatch, klines)

    counters = run_detector_cycle(now_ts=now_ts, db=session)

    assert counters == {"locked": 0, "settled": 0, "errors": 0}
    assert session.query(ArbOpportunityLog).count() == 0


def test_no_lock_when_sustained_time_too_short(monkeypatch, session):
    # Distance is ample (1%+) but the first close was on the OTHER side of the
    # strike, so the above-side streak only started at BASE_TS+120 -> 50s < 100s.
    klines = [
        _bar(BASE_TS, 100.0, 99.5),
        _bar(BASE_TS + 60, 99.5, 101.0),
        _bar(BASE_TS + 120, 101.0, 101.2),
    ]
    now_ts = BASE_TS + 170
    _patch_klines(monkeypatch, klines)

    counters = run_detector_cycle(now_ts=now_ts, db=session)

    assert counters == {"locked": 0, "settled": 0, "errors": 0}
    assert session.query(ArbOpportunityLog).count() == 0


def test_oscillating_price_never_locks(monkeypatch, session):
    # Closes alternate across the strike every minute: no side is ever held
    # long enough, in any of the overlapping windows, at any evaluation time.
    klines = [
        _bar(BASE_TS, 100.0, 101.0),
        _bar(BASE_TS + 60, 101.0, 99.0),
        _bar(BASE_TS + 120, 99.0, 101.0),
        _bar(BASE_TS + 180, 101.0, 99.0),
        _bar(BASE_TS + 240, 99.0, 101.0),  # forming at the last evaluation
    ]
    _patch_klines(monkeypatch, klines)

    for now_ts in (BASE_TS + 170, BASE_TS + 230, BASE_TS + 290):
        counters = run_detector_cycle(now_ts=now_ts, db=session)
        assert counters == {"locked": 0, "settled": 0, "errors": 0}

    assert session.query(ArbOpportunityLog).count() == 0


def test_no_duplicate_rows_for_same_window(monkeypatch, session):
    klines = [
        _bar(BASE_TS, 100.0, 101.0),
        _bar(BASE_TS + 60, 101.0, 101.2),
        _bar(BASE_TS + 120, 101.2, 101.5),
    ]
    _patch_klines(monkeypatch, klines)

    first = run_detector_cycle(now_ts=BASE_TS + 170, db=session)
    second = run_detector_cycle(now_ts=BASE_TS + 200, db=session)

    assert first["locked"] == 1
    assert second["locked"] == 0
    rows = session.query(ArbOpportunityLog).all()
    assert len(rows) == 1
    assert rows[0].locked_at == _naive_utc(BASE_TS + 170)  # original row untouched


# ---------------------------------------------------------------------------
# Settlement: rows are updated in place at window expiry
# ---------------------------------------------------------------------------


def test_settlement_win_for_locked_above(monkeypatch, session):
    row = _make_row(session, direction="above", strike=100.0)
    # Expiry bar (open time == window expiry BASE_TS+300) settles at its OPEN.
    klines = [_bar(BASE_TS + 300, 102.0, 102.5)]
    _patch_klines(monkeypatch, klines)

    counters = run_detector_cycle(now_ts=BASE_TS + 330, db=session)

    assert counters == {"locked": 0, "settled": 1, "errors": 0}
    session.refresh(row)
    assert row.outcome == "win"
    assert row.final_price == 102.0


def test_settlement_loss_for_locked_above(monkeypatch, session):
    row = _make_row(session, direction="above", strike=100.0)
    klines = [_bar(BASE_TS + 300, 99.0, 99.5)]
    _patch_klines(monkeypatch, klines)

    counters = run_detector_cycle(now_ts=BASE_TS + 330, db=session)

    assert counters == {"locked": 0, "settled": 1, "errors": 0}
    session.refresh(row)
    assert row.outcome == "loss"
    assert row.final_price == 99.0


def test_settlement_win_for_locked_below(monkeypatch, session):
    row = _make_row(session, direction="below", strike=100.0, distance_pct=0.8)
    klines = [_bar(BASE_TS + 300, 99.0, 99.5)]
    _patch_klines(monkeypatch, klines)

    counters = run_detector_cycle(now_ts=BASE_TS + 330, db=session)

    assert counters == {"locked": 0, "settled": 1, "errors": 0}
    session.refresh(row)
    assert row.outcome == "win"
    assert row.final_price == 99.0


def test_settlement_waits_for_expiry_bar(monkeypatch, session):
    row = _make_row(session)
    _patch_klines(monkeypatch, [])  # no bars at all: nothing to settle against

    counters = run_detector_cycle(now_ts=BASE_TS + 330, db=session)

    assert counters == {"locked": 0, "settled": 0, "errors": 0}
    session.refresh(row)
    assert row.outcome == "pending"
    assert row.final_price is None


def test_settlement_ignores_windows_not_yet_expired(monkeypatch, session):
    row = _make_row(session)
    klines = [_bar(BASE_TS + 240, 102.0, 102.1)]
    _patch_klines(monkeypatch, klines)

    counters = run_detector_cycle(now_ts=BASE_TS + 250, db=session)  # 50s to expiry

    assert counters["settled"] == 0
    session.refresh(row)
    assert row.outcome == "pending"


# ---------------------------------------------------------------------------
# Summary math (feeds GET /api/arb/summary)
# ---------------------------------------------------------------------------


def test_summary_math(monkeypatch, session):
    day1 = BASE_TS
    day2 = BASE_TS + 86400
    _make_row(session, window_start=_naive_utc(day1), locked_at=_naive_utc(day1 + 170),
              outcome="win", final_price=102.0)
    _make_row(session, window_start=_naive_utc(day1 + 600), locked_at=_naive_utc(day1 + 770),
              outcome="win", final_price=103.0)
    _make_row(session, window_start=_naive_utc(day1 + 1200), locked_at=_naive_utc(day1 + 1370),
              outcome="loss", final_price=99.0)
    _make_row(session, window_start=_naive_utc(day2), locked_at=_naive_utc(day2 + 170),
              outcome="loss", final_price=98.0)
    _make_row(session, window_start=_naive_utc(day2 + 600), locked_at=_naive_utc(day2 + 770),
              outcome="pending")

    summary = summarize_opportunities(session)

    assert summary["total"] == 5
    assert summary["pending"] == 1
    assert summary["wins"] == 2
    assert summary["losses"] == 2
    assert summary["decided"] == 4
    assert summary["lock_accuracy_pct"] == pytest.approx(50.0)

    daily = summary["daily"]
    assert [d["date"] for d in daily] == ["2026-07-08", "2026-07-09"]
    assert daily[0] == {"date": "2026-07-08", "count": 3, "wins": 2, "losses": 1, "pending": 0}
    assert daily[1] == {"date": "2026-07-09", "count": 2, "wins": 0, "losses": 1, "pending": 1}


def test_summary_with_no_rows(session):
    summary = summarize_opportunities(session)
    assert summary["total"] == 0
    assert summary["decided"] == 0
    assert summary["lock_accuracy_pct"] is None
    assert summary["daily"] == []


# ---------------------------------------------------------------------------
# Migration idempotency (sqlite-based: upgrade() twice must be harmless)
# ---------------------------------------------------------------------------


def test_arb_migration_upgrade_is_idempotent(monkeypatch):
    migration = importlib.import_module("database.migrations.add_arb_opportunity_log")
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(migration, "SessionLocal", factory)

    migration.upgrade()
    migration.upgrade()  # second run must be a no-op, not an error

    inspector = inspect(engine)
    assert inspector.has_table("arb_opportunity_log")
    columns = {col["name"] for col in inspector.get_columns("arb_opportunity_log")}
    assert {
        "id", "symbol", "window_start", "strike", "direction", "locked_at",
        "remaining_seconds", "distance_pct", "final_price", "outcome", "created_at",
    } <= columns


def test_arb_migration_is_registered():
    from database.migration_manager import MIGRATIONS

    assert "add_arb_opportunity_log.py" in MIGRATIONS
