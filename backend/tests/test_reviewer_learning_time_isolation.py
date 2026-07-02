"""Reviewer learning must only fit on trades settled BEFORE the backtest window."""
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from services.event_contract.reviewer_learning import fit_reviewer_stats
from services.event_contract.constants import EVENT_AI_NAMES

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
