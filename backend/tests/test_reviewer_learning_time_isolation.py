"""Reviewer learning must only fit on trades settled BEFORE the backtest window."""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from services.event_contract.reviewer_expertise import get_base_weight
from services.event_contract.reviewer_learning import (
    _CACHE,
    _CACHE_MAX_ENTRIES,
    _LATEST_CACHE_KEY,
    clear_reviewer_cache,
    compute_reviewer_weights,
    fit_reviewer_stats,
    invalidate_latest_reviewer_cache,
)
from services.event_contract.constants import EVENT_AI_NAMES
from services.event_contract_service import event_contract_service

REVIEWER = EVENT_AI_NAMES[0]


def _make_db():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE event_contract_trade_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_time TIMESTAMP,
                entry_price FLOAT,
                expiry_price FLOAT,
                ai_decision_snapshot TEXT
            )
            """
        ))
    return sessionmaker(bind=engine)()


def _insert_trade(db, entry_time: str, direction: str, won: bool):
    snapshot = json.dumps([{"ai_name": REVIEWER, "direction": direction, "confidence": 80}])
    entry, expiry = (100.0, 101.0) if (direction == "long") == won else (100.0, 99.0)
    db.execute(
        text(
            "INSERT INTO event_contract_trade_logs (entry_time, entry_price, expiry_price, ai_decision_snapshot)"
            " VALUES (:t, :e, :x, :s)"
        ),
        {"t": entry_time, "e": entry, "x": expiry, "s": snapshot},
    )
    db.commit()


def test_before_ts_excludes_in_window_trades():
    db = _make_db()
    _insert_trade(db, "2026-01-01 00:00:00", "long", won=True)   # pre-window
    _insert_trade(db, "2026-06-01 00:00:00", "long", won=True)   # in-window (must be excluded)
    cutoff = datetime(2026, 5, 1, tzinfo=timezone.utc)
    stats = fit_reviewer_stats(db, before_ts=cutoff)
    assert stats[REVIEWER].total == 1
    assert stats[REVIEWER].correct == 1


def test_no_before_ts_keeps_all_trades():
    db = _make_db()
    _insert_trade(db, "2026-01-01 00:00:00", "long", won=True)
    _insert_trade(db, "2026-06-01 00:00:00", "long", won=False)
    stats = fit_reviewer_stats(db)
    assert stats[REVIEWER].total == 2


def test_cache_evicts_oldest_beyond_cap():
    clear_reviewer_cache()
    db = _make_db()
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for i in range(_CACHE_MAX_ENTRIES + 1):
        compute_reviewer_weights(db, before_ts=base + timedelta(days=i))
    assert len(_CACHE) <= _CACHE_MAX_ENTRIES
    clear_reviewer_cache()


def test_invalidate_latest_reviewer_cache_pops_only_latest():
    clear_reviewer_cache()
    db = _make_db()
    cutoff = datetime(2026, 5, 1, tzinfo=timezone.utc)
    compute_reviewer_weights(db, before_ts=cutoff)
    compute_reviewer_weights(db)  # populates "__latest__"
    before_ts_key = cutoff.isoformat()
    assert before_ts_key in _CACHE
    assert _LATEST_CACHE_KEY in _CACHE

    invalidate_latest_reviewer_cache()

    assert before_ts_key in _CACHE
    assert _LATEST_CACHE_KEY not in _CACHE
    clear_reviewer_cache()


def test_normalize_config_rejects_bogus_reviewer_weights_mode():
    try:
        event_contract_service._normalize_config(
            {
                "symbol": "BTC",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-02T00:00:00Z",
                "reviewer_weights_mode": "bogus",
            },
            prediction=False,
        )
    except ValueError as exc:
        assert "reviewer_weights_mode" in str(exc)
    else:
        raise AssertionError("expected ValueError for bogus reviewer_weights_mode")


def test_load_reviewer_weights_static_mode_returns_base_weights():
    db = _make_db()
    weights = event_contract_service._load_reviewer_weights(db, {"reviewer_weights_mode": "static"})
    assert weights[REVIEWER] == get_base_weight(REVIEWER)
