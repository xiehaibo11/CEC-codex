"""TDD coverage for the paper-trader daily-statistics service (customer doc
section 4: the panel that resets at local midnight). "Today" is the current
calendar day in the requested timezone (default UTC+8); a bet belongs to today
when its SETTLEMENT (``expiry_time``) landed inside the local day, while
``opened_today`` counts bets whose ``decision_time`` landed inside it,
regardless of status.

All timestamps are naive UTC (matching the ORM columns) and "now" is injected
via the service's ``now`` parameter so nothing here depends on wall-clock,
mirroring how test_event_paper_auto_pause.py injects timestamps."""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from services.event_contract import paper_trader_api

# 2026-07-07 04:00 UTC == 2026-07-07 12:00 UTC+8, so the UTC+8 "today" window
# is [2026-07-06 16:00 UTC, 2026-07-07 16:00 UTC).
NOW_UTC = datetime(2026, 7, 7, 4, 0, 0)


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


@pytest.fixture()
def trader_id(session):
    trader = paper_trader_api.create_paper_trader(
        session,
        name="daily-stats-trader",
        config={"symbol": "BTC", "exchange": "binance"},
        allow_unvalidated=True,
    )
    return trader["id"]


def _add_bet(
    db,
    trader_id,
    *,
    status="settled",
    result=None,
    pnl=None,
    decision_time=None,
    expiry_time=None,
):
    bet = EventContractPaperBet(
        trader_id=trader_id,
        direction="long",
        status=status,
        decision_time=decision_time or datetime(2026, 7, 7, 3, 0, 0),
        expiry_time=expiry_time,
        stake=100.0,
        payout_ratio=0.8,
        result=result,
        pnl=pnl,
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


def _daily(session, trader_id, **kwargs):
    kwargs.setdefault("now", NOW_UTC)
    return paper_trader_api.get_paper_trader_daily_stats(session, trader_id, **kwargs)


class TestDayWindowSplit:
    def test_settled_today_vs_yesterday_split_under_utc8(self, session, trader_id):
        # Settled inside today's UTC+8 window.
        _add_bet(
            session, trader_id, result="win", pnl=80.0,
            decision_time=datetime(2026, 7, 7, 1, 0, 0),
            expiry_time=datetime(2026, 7, 7, 2, 0, 0),
        )
        # Settled yesterday (UTC+8): 2026-07-06 10:00 UTC is before 16:00 UTC.
        _add_bet(
            session, trader_id, result="loss", pnl=-100.0,
            decision_time=datetime(2026, 7, 6, 9, 0, 0),
            expiry_time=datetime(2026, 7, 6, 10, 0, 0),
        )

        stats = _daily(session, trader_id)
        assert stats["trader_id"] == trader_id
        assert stats["date"] == "2026-07-07"
        assert stats["tz_offset_minutes"] == 480
        assert stats["settled_today"] == 1
        assert stats["wins"] == 1
        assert stats["losses"] == 0
        assert stats["net_pnl"] == pytest.approx(80.0)
        # Only the bet opened today counts as opened_today.
        assert stats["opened_today"] == 1

    def test_utc_boundary_bet_counts_for_local_today(self, session, trader_id):
        # 2026-07-06 23:30 UTC == 2026-07-07 07:30 UTC+8 -> belongs to today.
        _add_bet(
            session, trader_id, result="win", pnl=80.0,
            decision_time=datetime(2026, 7, 6, 23, 0, 0),
            expiry_time=datetime(2026, 7, 6, 23, 30, 0),
        )
        # 2026-07-06 15:30 UTC == 2026-07-06 23:30 UTC+8 -> yesterday.
        _add_bet(
            session, trader_id, result="win", pnl=80.0,
            decision_time=datetime(2026, 7, 6, 15, 0, 0),
            expiry_time=datetime(2026, 7, 6, 15, 30, 0),
        )

        stats = _daily(session, trader_id)
        assert stats["settled_today"] == 1
        assert stats["opened_today"] == 1
        assert stats["wins"] == 1

    def test_tz_offset_zero_uses_utc_day(self, session, trader_id):
        # 2026-07-06 23:30 UTC is yesterday when the requested timezone is UTC.
        _add_bet(
            session, trader_id, result="win", pnl=80.0,
            decision_time=datetime(2026, 7, 6, 23, 0, 0),
            expiry_time=datetime(2026, 7, 6, 23, 30, 0),
        )
        stats = _daily(session, trader_id, tz_offset_minutes=0)
        assert stats["date"] == "2026-07-07"
        assert stats["tz_offset_minutes"] == 0
        assert stats["settled_today"] == 0
        assert stats["opened_today"] == 0


class TestOpenedToday:
    def test_opened_today_counts_pending_bets_from_today(self, session, trader_id):
        _add_bet(
            session, trader_id, status="pending_entry",
            decision_time=datetime(2026, 7, 7, 3, 30, 0),
        )
        _add_bet(
            session, trader_id, status="open",
            decision_time=datetime(2026, 7, 7, 3, 45, 0),
        )
        # Opened yesterday (UTC+8) -> not counted.
        _add_bet(
            session, trader_id, status="open",
            decision_time=datetime(2026, 7, 6, 12, 0, 0),
        )

        stats = _daily(session, trader_id)
        assert stats["opened_today"] == 2
        assert stats["settled_today"] == 0


class TestMath:
    def test_win_loss_amounts_and_rates(self, session, trader_id):
        for i in range(3):
            _add_bet(
                session, trader_id, result="win", pnl=80.0,
                decision_time=datetime(2026, 7, 7, 1, i, 0),
                expiry_time=datetime(2026, 7, 7, 2, i, 0),
            )
        for i in range(2):
            _add_bet(
                session, trader_id, result="loss", pnl=-100.0,
                decision_time=datetime(2026, 7, 7, 1, 30 + i, 0),
                expiry_time=datetime(2026, 7, 7, 2, 30 + i, 0),
            )
        _add_bet(
            session, trader_id, result="draw", pnl=0.0,
            decision_time=datetime(2026, 7, 7, 1, 45, 0),
            expiry_time=datetime(2026, 7, 7, 2, 45, 0),
        )

        stats = _daily(session, trader_id)
        assert stats["opened_today"] == 6
        assert stats["settled_today"] == 6
        assert stats["wins"] == 3
        assert stats["win_amount"] == pytest.approx(240.0)
        assert stats["losses"] == 2
        assert stats["loss_amount"] == pytest.approx(200.0)
        assert stats["draws"] == 1
        # Rates are over decided bets (wins + losses = 5); draws excluded.
        assert stats["win_rate_pct"] == pytest.approx(60.0)
        assert stats["loss_rate_pct"] == pytest.approx(40.0)
        assert stats["net_pnl"] == pytest.approx(40.0)

    def test_empty_day_returns_zeros(self, session, trader_id):
        stats = _daily(session, trader_id)
        assert stats == {
            "trader_id": trader_id,
            "date": "2026-07-07",
            "tz_offset_minutes": 480,
            "opened_today": 0,
            "settled_today": 0,
            "wins": 0,
            "win_amount": 0.0,
            "losses": 0,
            "loss_amount": 0.0,
            "draws": 0,
            "win_rate_pct": 0,
            "loss_rate_pct": 0,
            "net_pnl": 0.0,
        }


class TestErrors:
    def test_missing_trader_raises_value_error(self, session):
        with pytest.raises(ValueError, match="not found"):
            paper_trader_api.get_paper_trader_daily_stats(session, 9999, now=NOW_UTC)
