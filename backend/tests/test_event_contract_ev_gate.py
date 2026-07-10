"""TDD coverage for the historical expected-value gate (ev_gate).

Why it exists: 6867 deduplicated decided trades across every backtest run show
the current signal family at 42-52% win rate in every stratification - below
the 55.6% break-even at 0.8 payout. Configs that backtested above break-even
were selection-bias artifacts (best of 2036 runs). The gate makes each live
decision consult the deduplicated historical record of similar trades and
refuse to bet without demonstrated positive expectancy.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import (
    EventContractBacktestRun,
    EventContractTradeLog,
)
from services.event_contract import ev_gate

CUTOFF = dt.datetime(2026, 7, 1, 0, 0, 0)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[EventContractBacktestRun.__table__, EventContractTradeLog.__table__],
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    run = EventContractBacktestRun(
        symbol="BTC",
        exchange="binance",
        environment="mainnet",
        period="1m",
        start_time=dt.datetime(2026, 5, 1),
        end_time=dt.datetime(2026, 7, 4),
        status="completed",
    )
    db.add(run)
    db.commit()
    db.info["run_id"] = run.id
    try:
        yield db
    finally:
        db.close()


def _add_trade(db, entry_time, result, direction="short", market_state="breakout", run_id=None):
    trade = EventContractTradeLog(
        run_id=run_id or db.info["run_id"],
        trade_index=0,
        symbol="BTC",
        direction=direction,
        entry_time=entry_time,
        entry_price=100.0,
        expiry_time=entry_time + dt.timedelta(minutes=5),
        expiry_price=99.0 if result == "win" and direction == "short" else 101.0,
        result=result,
        profit_loss=80.0 if result == "win" else -100.0,
        market_state=market_state,
    )
    db.add(trade)
    db.commit()
    return trade


class TestEstimator:
    def test_counts_wins_and_losses_for_matching_cell(self, session):
        base = dt.datetime(2026, 6, 1, 0, 0, 0)
        for i in range(6):
            _add_trade(session, base + dt.timedelta(hours=i), "win")
        for i in range(4):
            _add_trade(session, base + dt.timedelta(hours=10 + i), "loss")

        est = ev_gate.estimate_historical_win_rate(
            session, symbol="BTC", direction="short", market_state="breakout", cutoff=CUTOFF
        )
        assert est["n"] == 10
        assert est["wins"] == 6
        assert est["win_rate"] == pytest.approx(60.0)
        assert 0 < est["ci_low"] < 60.0 < est["ci_high"] <= 100.0

    def test_dedupes_identical_market_events_across_runs(self, session):
        """The same (symbol, direction, entry_time) traded by 5 different
        backtest runs is ONE market event, not five samples."""
        run2 = EventContractBacktestRun(
            symbol="BTC", exchange="binance", environment="mainnet", period="1m",
            start_time=dt.datetime(2026, 5, 1), end_time=dt.datetime(2026, 7, 4),
            status="completed",
        )
        session.add(run2)
        session.commit()

        ts = dt.datetime(2026, 6, 1, 12, 0, 0)
        _add_trade(session, ts, "win")
        _add_trade(session, ts, "win", run_id=run2.id)

        est = ev_gate.estimate_historical_win_rate(
            session, symbol="BTC", direction="short", market_state="breakout", cutoff=CUTOFF
        )
        assert est["n"] == 1

    def test_cutoff_excludes_trades_at_or_after_decision_time(self, session):
        """Leakage guard: a backtest replaying June must not see July outcomes."""
        _add_trade(session, dt.datetime(2026, 6, 30, 23, 0, 0), "win")
        _add_trade(session, CUTOFF, "win")
        _add_trade(session, dt.datetime(2026, 7, 2, 0, 0, 0), "win")

        est = ev_gate.estimate_historical_win_rate(
            session, symbol="BTC", direction="short", market_state="breakout", cutoff=CUTOFF
        )
        assert est["n"] == 1

    def test_filters_by_direction_and_market_state(self, session):
        _add_trade(session, dt.datetime(2026, 6, 1), "win", direction="short", market_state="breakout")
        _add_trade(session, dt.datetime(2026, 6, 2), "loss", direction="long", market_state="breakout")
        _add_trade(session, dt.datetime(2026, 6, 3), "loss", direction="short", market_state="trend_up")

        est = ev_gate.estimate_historical_win_rate(
            session, symbol="BTC", direction="short", market_state="breakout", cutoff=CUTOFF
        )
        assert est["n"] == 1
        assert est["wins"] == 1


class TestGate:
    def _seed(self, session, wins, losses):
        base = dt.datetime(2026, 6, 1)
        for i in range(wins):
            _add_trade(session, base + dt.timedelta(minutes=10 * i), "win")
        for i in range(losses):
            _add_trade(session, base + dt.timedelta(minutes=10 * (wins + i)), "loss")

    def test_blocks_when_history_below_break_even(self, session):
        # 47% over 100 events - the real family's profile. Must block.
        self._seed(session, 47, 53)
        verdict = ev_gate.check_ev_gate(
            session, symbol="BTC", direction="short", market_state="breakout",
            cutoff=CUTOFF, break_even_pct=55.61,
        )
        assert verdict["allowed"] is False
        assert "55.61" in verdict["reason"]

    def test_blocks_on_insufficient_sample(self, session):
        # 8/10 looks great but n < 50: no demonstrated edge yet.
        self._seed(session, 8, 2)
        verdict = ev_gate.check_ev_gate(
            session, symbol="BTC", direction="short", market_state="breakout",
            cutoff=CUTOFF, break_even_pct=55.61,
        )
        assert verdict["allowed"] is False
        assert verdict["estimate"]["n"] == 10

    def test_allows_when_wilson_lower_bound_clears_break_even(self, session):
        # 130/180 = 72.2%, Wilson lower bound ~65% > 55.61: demonstrated edge.
        self._seed(session, 130, 50)
        verdict = ev_gate.check_ev_gate(
            session, symbol="BTC", direction="short", market_state="breakout",
            cutoff=CUTOFF, break_even_pct=55.61,
        )
        assert verdict["allowed"] is True
        assert verdict["estimate"]["ci_low"] > 55.61

    def test_blocks_when_mean_clears_but_lower_bound_does_not(self, session):
        # 34/60 = 56.7% mean is above break-even but Wilson LB ~44% is not:
        # not yet statistically demonstrated.
        self._seed(session, 34, 26)
        verdict = ev_gate.check_ev_gate(
            session, symbol="BTC", direction="short", market_state="breakout",
            cutoff=CUTOFF, break_even_pct=55.61,
        )
        assert verdict["allowed"] is False


class TestReport:
    def test_report_splits_trades_by_gate_verdict(self, session):
        # History: 60 wins / 120 events before July (50% - blocks).
        base = dt.datetime(2026, 6, 1)
        for i in range(60):
            _add_trade(session, base + dt.timedelta(minutes=10 * i), "win")
        for i in range(60):
            _add_trade(session, base + dt.timedelta(minutes=10 * (60 + i)), "loss")

        trades = [
            {
                "symbol": "BTC",
                "direction": "short",
                "market_state": "breakout",
                "entry_time": "2026-07-02T10:00:00Z",
                "result": "loss",
            },
            {
                "symbol": "BTC",
                "direction": "short",
                "market_state": "breakout",
                "entry_time": "2026-07-02T11:00:00Z",
                "result": "win",
            },
        ]
        report = ev_gate.ev_gate_report(session, trades, break_even_pct=55.61)
        assert report["evaluated"] == 2
        assert report["allowed"] == 0
        assert report["blocked"] == 2
        assert report["blocked_win_rate"] == pytest.approx(50.0)
