"""Prompt-backtest replays must carry the same risk-guard verdicts as live.

Without this, a prompt variant that "fixes" the 2026-07-06 narrative-selling
looks good in backtest while its decisions would be rejected live (or vice
versa) - sim/live divergence in exactly the place the guard matters most.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.accounts_auth import Account
from database.models.trading import AIDecisionLog
from services.prompt_backtest_service import _annotate_live_risk_guard

NOW = dt.datetime(2026, 7, 6, 15, 0, 0)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Account.__table__, AIDecisionLog.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    account = Account(user_id=1, name="parity-test", account_type="AI", is_active="true")
    db.add(account)
    db.commit()
    db.info["account_id"] = account.id
    try:
        yield db
    finally:
        db.close()


def _add(db, operation, pnl, minutes_before):
    db.add(
        AIDecisionLog(
            account_id=db.info["account_id"],
            decision_time=NOW - dt.timedelta(minutes=minutes_before),
            reason="r",
            operation=operation,
            symbol="BTC",
            target_portion=0.2,
            total_balance=1000.0,
            executed="true",
            realized_pnl=pnl,
            exchange="binance",
        )
    )
    db.commit()


def test_replay_blocks_direction_frozen_at_that_moment(session):
    _add(session, "sell", -16.75, 120)
    _add(session, "sell", -27.58, 60)

    decision = {"operation": "sell", "symbol": "BTC"}
    _annotate_live_risk_guard(
        session, decision, account_id=session.info["account_id"], decision_time=NOW
    )
    assert "风控闸" in decision["_risk_guard_blocked"]


def test_replay_ignores_losses_after_the_replayed_moment(session):
    """Losses that happened AFTER the historical decision must not leak back."""
    _add(session, "sell", -16.75, -60)   # 1h AFTER the replayed moment
    _add(session, "sell", -27.58, -120)  # 2h AFTER

    decision = {"operation": "sell", "symbol": "BTC"}
    _annotate_live_risk_guard(
        session, decision, account_id=session.info["account_id"], decision_time=NOW
    )
    assert "_risk_guard_blocked" not in decision


def test_replay_leaves_clean_directions_untouched(session):
    _add(session, "sell", -16.75, 120)
    _add(session, "sell", 12.0, 60)

    decision = {"operation": "sell", "symbol": "BTC"}
    _annotate_live_risk_guard(
        session, decision, account_id=session.info["account_id"], decision_time=NOW
    )
    assert "_risk_guard_blocked" not in decision


def test_replay_skips_hold_and_missing_context(session):
    for decision, kwargs in (
        ({"operation": "hold", "symbol": "BTC"}, {"account_id": 1, "decision_time": NOW}),
        ({"operation": "sell", "symbol": "BTC"}, {"account_id": None, "decision_time": NOW}),
        ({"operation": "sell", "symbol": "BTC"}, {"account_id": 1, "decision_time": None}),
    ):
        _annotate_live_risk_guard(session, decision, **kwargs)
        assert "_risk_guard_blocked" not in decision
