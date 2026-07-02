"""TDD coverage for the event-contract dimension of attribution analytics
(spec module 2, task 5): `build_event_contract_attribution` reads settled
EventContractPaperBet rows and returns overview (Wilson CI on decided
win-rate) + direction/market_state/hour-bucket breakdowns. Runs against an
in-memory sqlite session; the route file is a thin shell (no TestClient
needed per the task brief)."""
from __future__ import annotations

import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from api.analytics_event_contract import build_event_contract_attribution
from services.event_contract.backtest_stats import wilson_interval


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[EventContractPaperTrader.__table__, EventContractPaperBet.__table__]
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _make_trader(db, name="trader-1"):
    trader = EventContractPaperTrader(
        name=name,
        symbol="BTC",
        exchange="binance",
        environment="mainnet",
        config="{}",
        stake_amount=100.0,
        initial_balance=10000.0,
        current_balance=10000.0,
    )
    db.add(trader)
    db.commit()
    db.refresh(trader)
    return trader


def _add_bet(
    db,
    trader_id,
    *,
    direction="long",
    market_state="trend",
    hour=0,
    result="win",
    pnl=80.0,
    status="settled",
    day=1,
):
    bet = EventContractPaperBet(
        trader_id=trader_id,
        direction=direction,
        status=status,
        decision_time=datetime.datetime(2026, 7, day, hour, 0, 0),
        stake=100.0,
        payout_ratio=0.8,
        result=result,
        pnl=pnl,
        market_state=market_state,
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


# 3 wins / 2 losses / 1 draw across directions/states/hours, matching the
# task brief's "3W/2L/1D" fixture.
def _seed_known_bets(db, trader_id):
    # long / trend / hour 1 -> bucket h00-03
    _add_bet(db, trader_id, direction="long", market_state="trend", hour=1, result="win", pnl=80.0)
    _add_bet(db, trader_id, direction="long", market_state="trend", hour=2, result="win", pnl=80.0)
    # short / range / hour 5 -> bucket h04-07
    _add_bet(db, trader_id, direction="short", market_state="range", hour=5, result="win", pnl=80.0)
    _add_bet(db, trader_id, direction="short", market_state="range", hour=6, result="loss", pnl=-100.0)
    # long / trend / hour 9 -> bucket h08-11
    _add_bet(db, trader_id, direction="long", market_state="trend", hour=9, result="loss", pnl=-100.0)
    # short / range / hour 13 -> bucket h12-15 (draw)
    _add_bet(db, trader_id, direction="short", market_state="range", hour=13, result="draw", pnl=0.0)


class TestOverviewMath:
    def test_known_wins_losses_draws(self, session):
        trader = _make_trader(session)
        _seed_known_bets(session, trader.id)

        result = build_event_contract_attribution(session)
        overview = result["overview"]

        assert overview["n"] == 6
        assert overview["wins"] == 3
        assert overview["losses"] == 2
        assert overview["draws"] == 1
        assert overview["decided"] == 5
        assert overview["decided_win_rate"] == pytest.approx(60.0)

        expected_lo, expected_hi = wilson_interval(3, 5)
        assert overview["win_rate_ci_low"] == expected_lo
        assert overview["win_rate_ci_high"] == expected_hi

        assert overview["total_pnl"] == pytest.approx(80 + 80 + 80 - 100 - 100 + 0)

    def test_only_settled_bets_counted(self, session):
        trader = _make_trader(session)
        _add_bet(session, trader.id, result="win", pnl=80.0, status="settled")
        session.add(
            EventContractPaperBet(
                trader_id=trader.id,
                direction="long",
                status="open",
                decision_time=datetime.datetime(2026, 7, 1, 3, 0, 0),
                stake=100.0,
                payout_ratio=0.8,
            )
        )
        session.commit()

        overview = build_event_contract_attribution(session)["overview"]
        assert overview["n"] == 1

    def test_empty_returns_zeroed_overview(self, session):
        overview = build_event_contract_attribution(session)["overview"]
        assert overview["n"] == 0
        assert overview["decided"] == 0
        assert overview["decided_win_rate"] == 0
        assert overview["win_rate_ci_low"] == 0.0
        assert overview["win_rate_ci_high"] == 0.0
        assert overview["total_pnl"] == 0


class TestDimensionBreakdowns:
    def test_by_direction(self, session):
        trader = _make_trader(session)
        _seed_known_bets(session, trader.id)

        rows = build_event_contract_attribution(session)["by_direction"]
        by_key = {row["key"]: row for row in rows}

        assert by_key["long"]["n"] == 3
        assert by_key["long"]["win_rate"] == pytest.approx(2 / 3 * 100, abs=0.01)
        assert by_key["long"]["pnl"] == pytest.approx(80 + 80 - 100)

        assert by_key["short"]["n"] == 3
        assert by_key["short"]["win_rate"] == pytest.approx(1 / 2 * 100, abs=0.01)  # 1 win, 1 loss, 1 draw
        assert by_key["short"]["pnl"] == pytest.approx(80 - 100 + 0)

    def test_by_market_state(self, session):
        trader = _make_trader(session)
        _seed_known_bets(session, trader.id)

        rows = build_event_contract_attribution(session)["by_market_state"]
        by_key = {row["key"]: row for row in rows}

        assert by_key["trend"]["n"] == 3
        assert by_key["trend"]["win_rate"] == pytest.approx(2 / 3 * 100, abs=0.01)
        assert by_key["range"]["n"] == 3
        assert by_key["range"]["win_rate"] == pytest.approx(1 / 2 * 100, abs=0.01)

    def test_by_hour_bucket_keys_and_counts(self, session):
        trader = _make_trader(session)
        _seed_known_bets(session, trader.id)

        rows = build_event_contract_attribution(session)["by_hour_bucket"]
        keys = [row["key"] for row in rows]
        assert keys == [
            "h00-03", "h04-07", "h08-11", "h12-15", "h16-19", "h20-23",
        ]

        by_key = {row["key"]: row for row in rows}
        assert by_key["h00-03"]["n"] == 2  # hours 1, 2
        assert by_key["h04-07"]["n"] == 2  # hours 5, 6
        assert by_key["h08-11"]["n"] == 1  # hour 9
        assert by_key["h12-15"]["n"] == 1  # hour 13 (draw)
        assert by_key["h16-19"]["n"] == 0
        assert by_key["h20-23"]["n"] == 0

        assert by_key["h04-07"]["win_rate"] == pytest.approx(50.0)  # 1 win, 1 loss
        assert by_key["h12-15"]["win_rate"] == 0  # only a draw -> 0 decided


class TestTraderFilter:
    def test_trader_id_scopes_results(self, session):
        trader_a = _make_trader(session, name="trader-a")
        trader_b = _make_trader(session, name="trader-b")
        _add_bet(session, trader_a.id, result="win", pnl=80.0)
        _add_bet(session, trader_a.id, result="win", pnl=80.0)
        _add_bet(session, trader_b.id, result="loss", pnl=-100.0)

        result_a = build_event_contract_attribution(session, trader_id=trader_a.id)
        assert result_a["overview"]["n"] == 2
        assert result_a["overview"]["wins"] == 2

        result_b = build_event_contract_attribution(session, trader_id=trader_b.id)
        assert result_b["overview"]["n"] == 1
        assert result_b["overview"]["losses"] == 1

        result_all = build_event_contract_attribution(session)
        assert result_all["overview"]["n"] == 3


class TestPeriodFilter:
    def test_start_end_filter_by_decision_time(self, session):
        trader = _make_trader(session)
        _add_bet(session, trader.id, result="win", pnl=80.0, day=1)
        _add_bet(session, trader.id, result="loss", pnl=-100.0, day=5)
        _add_bet(session, trader.id, result="win", pnl=80.0, day=10)

        result = build_event_contract_attribution(
            session,
            start=datetime.datetime(2026, 7, 3),
            end=datetime.datetime(2026, 7, 8),
        )
        assert result["overview"]["n"] == 1
        assert result["overview"]["losses"] == 1
