from services.ai_review.agents.backtest_reviewer import BacktestReviewer
from services.ai_review.agents.loss_reviewer import LossReviewer
from services.ai_review.agents.signal_reviewer import SignalReviewer
from services.ai_review.schemas import AgentVerdict, ReviewContext

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.accounts_auth import Account
from database.models.trading import AIDecisionLog


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Account.__table__, AIDecisionLog.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _ctx(**overrides):
    data = {
        "account_id": 1,
        "account_name": "bot",
        "exchange": "binance",
        "environment": "mainnet",
        "symbol": "BTC",
        "operation": "buy",
        "decision": {"operation": "buy", "symbol": "BTC"},
        "portfolio": {"total_assets": 1000},
        "positions": [],
        "prices": {"BTC": 65000},
        "trigger_context": {"trigger_type": "scheduled"},
    }
    data.update(overrides)
    return ReviewContext(**data)


def test_signal_reviewer_passes_non_opening_trade(session):
    report = SignalReviewer().review(session, _ctx(operation="close"))
    assert report.verdict == AgentVerdict.PASS


def test_signal_reviewer_blocks_scheduled_open_without_signal(session):
    report = SignalReviewer().review(session, _ctx(trigger_context={"trigger_type": "scheduled"}))
    assert report.verdict == AgentVerdict.BLOCK
    assert "非信号触发" in report.blocking_reasons[0]


def test_backtest_reviewer_warns_when_signal_has_no_backtest_summary(session):
    report = BacktestReviewer().review(session, _ctx(trigger_context={"trigger_type": "signal"}))
    assert report.verdict == AgentVerdict.WARN
    assert "缺少回测摘要" in report.warnings[0]


def test_backtest_reviewer_blocks_explicit_negative_backtest(session):
    report = BacktestReviewer().review(
        session,
        _ctx(trigger_context={"trigger_type": "signal", "backtest_summary": {"net_pnl": -12.5, "target_sample_met": True}}),
    )
    assert report.verdict == AgentVerdict.BLOCK
    assert "净盈亏为负" in report.blocking_reasons[0]


def test_loss_reviewer_blocks_existing_risk_guard_failure(session):
    report = LossReviewer().review(
        session,
        _ctx(positions=[{"coin": "BTC", "szi": 1.0, "position_value": 500, "unrealized_pnl": -15.0}]),
    )
    assert report.verdict == AgentVerdict.BLOCK
    assert "风控闸" in report.blocking_reasons[0]
