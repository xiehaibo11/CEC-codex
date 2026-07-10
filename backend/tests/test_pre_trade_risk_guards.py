"""TDD coverage for deterministic pre-trade risk guards on AI decisions.

Evidence from Binance testnet account 3 (2026-07-06):
- The scheduled LLM repeated the same bearish news thesis FIVE times in three
  hours (12:17-15:03), every executed sell realizing a loss (-4.32, -16.75,
  -27.58, -16.21, -12.71). Nothing stopped attempt #3 after #1 and #2 lost.
- Same-direction exposure stacked unbounded (short notional 0.195 -> 1.06 of
  equity; DEPTH_RATIO longs earlier crept to ~97% margin usage) until the
  post-hoc margin monitor force-closed - risk control acting as exit strategy.

The guards are deliberately dumb and deterministic: no alpha, pure hygiene.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.accounts_auth import Account
from database.models.trading import AIDecisionLog
from services.trading_commands.risk_guards import check_pre_trade_guards

NOW = dt.datetime(2026, 7, 6, 15, 0, 0)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Account.__table__, AIDecisionLog.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    account = Account(user_id=1, name="guard-test", account_type="AI", is_active="true")
    db.add(account)
    db.commit()
    db.info["account_id"] = account.id
    try:
        yield db
    finally:
        db.close()


def _add_decision(db, operation, pnl, minutes_ago, symbol="BTC", executed="true"):
    log = AIDecisionLog(
        account_id=db.info["account_id"],
        decision_time=NOW - dt.timedelta(minutes=minutes_ago),
        reason="test decision",
        operation=operation,
        symbol=symbol,
        target_portion=0.2,
        total_balance=1000.0,
        executed=executed,
        realized_pnl=pnl,
        exchange="binance",
    )
    db.add(log)
    db.commit()
    return log


def _position(coin="BTC", szi=0.0, position_value=0.0):
    return {"coin": coin, "szi": szi, "position_value": position_value}


class TestLossStreakGuard:
    def test_blocks_after_two_consecutive_same_direction_losses(self, session):
        _add_decision(session, "sell", -16.75, minutes_ago=90)
        _add_decision(session, "sell", -27.58, minutes_ago=45)

        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=[], total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is False
        assert "连续" in verdict["reason"] or "loss" in verdict["reason"].lower()

    def test_opposite_direction_not_blocked(self, session):
        _add_decision(session, "sell", -16.75, minutes_ago=90)
        _add_decision(session, "sell", -27.58, minutes_ago=45)

        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="buy", positions=[], total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True

    def test_win_resets_the_streak(self, session):
        _add_decision(session, "sell", -16.75, minutes_ago=90)
        _add_decision(session, "sell", 12.00, minutes_ago=60)
        _add_decision(session, "sell", -27.58, minutes_ago=30)

        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=[], total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True

    def test_old_losses_outside_lookback_ignored(self, session):
        _add_decision(session, "sell", -16.75, minutes_ago=60 * 30)
        _add_decision(session, "sell", -27.58, minutes_ago=60 * 26)

        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=[], total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True

    def test_unsettled_and_unexecuted_decisions_ignored(self, session):
        _add_decision(session, "sell", None, minutes_ago=90)
        _add_decision(session, "sell", 0, minutes_ago=60)
        _add_decision(session, "sell", -27.58, minutes_ago=30, executed="false")

        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=[], total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True

    def test_other_symbol_losses_do_not_block(self, session):
        _add_decision(session, "sell", -16.75, minutes_ago=90, symbol="ETH")
        _add_decision(session, "sell", -27.58, minutes_ago=45, symbol="ETH")

        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=[], total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True


class TestExposureCapGuard:
    def test_blocks_add_when_same_direction_exposure_at_cap(self, session):
        # Existing short worth 2.1x equity; another sell must be blocked.
        positions = [_position(szi=-0.033, position_value=2100.0)]
        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=positions, total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is False
        assert "敞口" in verdict["reason"] or "exposure" in verdict["reason"].lower()

    def test_allows_add_below_cap(self, session):
        positions = [_position(szi=-0.01, position_value=600.0)]
        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=positions, total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True

    def test_opposite_direction_open_not_blocked_by_exposure(self, session):
        # A large short does not block a buy (which reduces/hedges).
        positions = [_position(szi=-0.033, position_value=2100.0)]
        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="buy", positions=positions, total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True

    def test_zero_equity_blocks_new_exposure(self, session):
        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=[], total_equity=0.0, now=NOW,
        )
        assert verdict["allowed"] is False


class TestGuardScope:
    def test_hold_and_close_never_blocked(self, session):
        _add_decision(session, "sell", -16.75, minutes_ago=90)
        _add_decision(session, "sell", -27.58, minutes_ago=45)
        positions = [_position(szi=-0.033, position_value=9000.0)]

        for operation in ("hold", "close"):
            verdict = check_pre_trade_guards(
                session, account_id=session.info["account_id"], symbol="BTC",
                operation=operation, positions=positions, total_equity=1000.0, now=NOW,
            )
            assert verdict["allowed"] is True, operation


class TestBinanceExecutorWiring:
    """A guard-blocked decision must never reach the exchange client and must
    be persisted as executed=False with the guard reason attached."""

    class _ExplodingClient:
        def place_order_with_tpsl(self, *a, **k):
            raise AssertionError("order must not be placed when guard blocks")

    def test_blocked_sell_never_reaches_client(self, session, monkeypatch):
        from services.trading_commands import binance_execution

        _add_decision(session, "sell", -16.75, minutes_ago=90)
        _add_decision(session, "sell", -27.58, minutes_ago=45)

        saved = []

        def _fake_save(db, account, decision, portfolio, executed, **kwargs):
            saved.append({"decision": decision, "executed": executed})

        monkeypatch.setattr(binance_execution, "save_ai_decision", _fake_save)
        monkeypatch.setattr(
            "services.trading_commands.risk_guards.datetime",
            type("_dt", (), {"utcnow": staticmethod(lambda: NOW)}),
        )

        account = session.query(Account).first()
        binance_execution._execute_binance_decision(
            session,
            account,
            self._ExplodingClient(),
            {
                "operation": "sell",
                "symbol": "BTC",
                "target_portion_of_balance": 0.2,
                "leverage": 5,
                "reason": "same bearish thesis again",
            },
            portfolio={"total_assets": 1000.0},
            positions=[],
            prices={"BTC": 62000.0},
            available_balance=900.0,
        )

        assert len(saved) == 1
        assert saved[0]["executed"] is False
        assert "风控闸" in saved[0]["decision"]["_risk_guard_blocked"]


class TestLosingPositionAddGuard:
    """Rule patch extracted from loss attribution (2026-07-08): 70% of settled
    losses carried the stacking_add tag (-88.29 net). Adding to a position
    that is currently under water is averaging into a disproven thesis."""

    def test_blocks_add_to_losing_same_direction_position(self, session):
        positions = [
            {"coin": "BTC", "szi": -0.01, "position_value": 600.0, "unrealized_pnl": -25.0}
        ]
        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=positions, total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is False
        assert "亏损" in verdict["reason"]

    def test_allows_add_to_winning_position(self, session):
        positions = [
            {"coin": "BTC", "szi": -0.01, "position_value": 600.0, "unrealized_pnl": 30.0}
        ]
        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="sell", positions=positions, total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True

    def test_opposite_direction_not_blocked_by_losing_position(self, session):
        positions = [
            {"coin": "BTC", "szi": -0.01, "position_value": 600.0, "unrealized_pnl": -25.0}
        ]
        verdict = check_pre_trade_guards(
            session, account_id=session.info["account_id"], symbol="BTC",
            operation="buy", positions=positions, total_equity=1000.0, now=NOW,
        )
        assert verdict["allowed"] is True
