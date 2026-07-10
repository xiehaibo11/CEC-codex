"""The LLM must SEE its recent settled outcomes per direction before deciding.

2026-07-06 evidence: the scheduled LLM repeated one bearish thesis five times,
every sell realizing a loss. The prompt showed recent trades but never said
"this direction has just lost N times in a row" - so the model kept treating
each cycle as a fresh question. This section makes the streak explicit and
warns that the hard risk guard will reject the direction once frozen.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.accounts_auth import Account
from database.models.trading import AIDecisionLog
from services.ai_decision_service.prompt_runtime_sections import (
    build_decision_outcome_context,
)

NOW = dt.datetime(2026, 7, 6, 15, 30, 0)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Account.__table__, AIDecisionLog.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    account = Account(user_id=1, name="ctx-test", account_type="AI", is_active="true")
    db.add(account)
    db.commit()
    db.info["account_id"] = account.id
    try:
        yield db
    finally:
        db.close()


def _add(db, operation, pnl, minutes_ago, symbol="BTC"):
    db.add(
        AIDecisionLog(
            account_id=db.info["account_id"],
            decision_time=NOW - dt.timedelta(minutes=minutes_ago),
            reason="r",
            operation=operation,
            symbol=symbol,
            target_portion=0.2,
            total_balance=1000.0,
            executed="true",
            realized_pnl=pnl,
            exchange="binance",
        )
    )
    db.commit()


def test_empty_history_returns_empty_string(session):
    assert build_decision_outcome_context(
        session, session.info["account_id"], now=NOW
    ) == ""


def test_summarizes_outcomes_per_symbol_direction(session):
    _add(session, "sell", -16.75, 180)
    _add(session, "sell", -27.58, 120)
    _add(session, "buy", 31.46, 60)

    text = build_decision_outcome_context(session, session.info["account_id"], now=NOW)
    assert "BTC sell" in text
    assert "BTC buy" in text
    assert "-44.33" in text  # sell direction net pnl


def test_frozen_direction_carries_hard_warning(session):
    _add(session, "sell", -16.75, 180)
    _add(session, "sell", -27.58, 120)

    text = build_decision_outcome_context(session, session.info["account_id"], now=NOW)
    assert "连续亏损 2" in text
    assert "风控闸" in text  # tells the model the direction is frozen


def test_single_loss_gets_soft_warning_only(session):
    _add(session, "sell", -16.75, 60)

    text = build_decision_outcome_context(session, session.info["account_id"], now=NOW)
    assert "连续亏损 1" in text
    assert "风控闸" not in text


def test_win_after_losses_resets_warning(session):
    _add(session, "sell", -16.75, 180)
    _add(session, "sell", -27.58, 120)
    _add(session, "sell", 12.0, 30)

    text = build_decision_outcome_context(session, session.info["account_id"], now=NOW)
    assert "连续亏损" not in text


class TestCriticalConstraintsTail:
    """System facts belong at the END of the prompt (verified lost-in-the-middle
    research: attention is U-shaped; mid-context constraints get skipped)."""

    def test_frozen_direction_surfaces_in_tail(self, session):
        from services.ai_decision_service.prompt_runtime_sections import (
            build_critical_constraints_tail,
        )

        _add(session, "sell", -16.75, 180)
        _add(session, "sell", -27.58, 120)

        tail = build_critical_constraints_tail(
            session, session.info["account_id"], ["BTC"],
            margin_usage_percent=42.5, now=NOW,
        )
        assert "BTC sell" in tail
        assert "冻结" in tail
        assert "42.5" in tail

    def test_tail_always_carries_hard_rules(self, session):
        from services.ai_decision_service.prompt_runtime_sections import (
            build_critical_constraints_tail,
        )

        tail = build_critical_constraints_tail(
            session, session.info["account_id"], ["BTC"], now=NOW,
        )
        assert "系统" in tail
        assert "N.Nh ago" in tail
