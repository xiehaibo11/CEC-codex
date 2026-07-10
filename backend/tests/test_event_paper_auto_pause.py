"""TDD coverage for the paper-trader auto-pause kill switch.

Root cause being guarded: an overfit/unvalidated config can keep betting
forever while its forward win rate sits statistically below break-even
(trader #2 shipped with a fingerprint that had zero backtest runs and bled
6/9 losses). The cycle must falsify the edge and stop the trader on its own.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from services.event_contract.live_paper_trader import run_live_paper_cycle
from services.event_contract_service import event_contract_service

BASE_TS = int(datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc).timestamp())


def _naive_utc(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)


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


def _make_trader(db, **overrides):
    defaults = dict(
        name=overrides.pop("name", "auto-pause-trader"),
        enabled=True,
        symbol="BTC",
        exchange="binance",
        environment="mainnet",
        config="{}",
        stake_amount=100.0,
        initial_balance=10000.0,
        current_balance=10000.0,
    )
    defaults.update(overrides)
    trader = EventContractPaperTrader(**defaults)
    db.add(trader)
    db.commit()
    db.refresh(trader)
    return trader


def _bar(ts, open_price, close_price=None):
    close_price = open_price if close_price is None else close_price
    return {
        "timestamp": ts,
        "open": open_price,
        "high": max(open_price, close_price) + 0.5,
        "low": min(open_price, close_price) - 0.5,
        "close": close_price,
        "volume": 10.0,
    }


def _add_settled_losses(db, trader, count, start_ts):
    for i in range(count):
        decision_ts = start_ts + i * 600
        db.add(
            EventContractPaperBet(
                trader_id=trader.id,
                direction="long",
                status="settled",
                decision_time=_naive_utc(decision_ts),
                entry_time=_naive_utc(decision_ts),
                entry_price=100.0,
                expiry_time=_naive_utc(decision_ts + 300),
                expiry_price=99.0,
                result="loss",
                pnl=-100.0,
                stake=100.0,
                payout_ratio=0.8,
            )
        )
    db.commit()


def _add_due_losing_bet(db, trader, expiry_ts):
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="open",
        decision_time=_naive_utc(expiry_ts - 300),
        entry_time=_naive_utc(expiry_ts - 300),
        entry_price=100.0,
        expiry_time=_naive_utc(expiry_ts),
        stake=100.0,
        payout_ratio=0.8,
    )
    db.add(bet)
    db.commit()
    return bet


def _patch_market(monkeypatch, klines):
    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)

    def _fail_predict(*a, **k):
        raise AssertionError("predict must not run in this test")

    monkeypatch.setattr(event_contract_service, "predict", _fail_predict)


def test_auto_pause_fires_when_win_rate_significantly_below_breakeven(monkeypatch, session):
    """13 settled losses + 1 more settling this cycle = 0/14 decided. At 0.8
    payout the break-even win rate is 55.6%; P(0 wins in 14 | p=0.556) ~ 1e-5,
    so the trader must be disabled with an auto_pause stamp in its config."""
    trader = _make_trader(session)
    _add_settled_losses(session, trader, 13, BASE_TS - 20_000)
    _add_due_losing_bet(session, trader, BASE_TS)

    # Expiry bar opens below the 100.0 entry -> the long settles as a loss.
    _patch_market(monkeypatch, [_bar(BASE_TS, 99.0)])

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert counters["settled"] == 1
    session.refresh(trader)
    assert trader.enabled is False
    stamped = json.loads(trader.config)["auto_pause"]
    assert stamped["decided"] == 14
    assert stamped["wins"] == 0
    assert stamped["p_value"] < 0.05
    assert stamped["break_even_win_rate"] == pytest.approx(55.61, abs=0.1)


def test_auto_pause_waits_for_min_decided_sample(monkeypatch, session):
    """4 prior losses + 1 settling = 5 decided < 12 minimum: noise, keep going."""
    trader = _make_trader(session)
    _add_settled_losses(session, trader, 4, BASE_TS - 20_000)
    _add_due_losing_bet(session, trader, BASE_TS)

    _patch_market(monkeypatch, [_bar(BASE_TS, 99.0)])

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert counters["settled"] == 1
    session.refresh(trader)
    assert trader.enabled is True
    assert "auto_pause" not in json.loads(trader.config)


def test_auto_pause_not_triggered_by_breakeven_performance(monkeypatch, session):
    """A trader winning near break-even must not be paused: 9 wins / 15 decided
    (60%) sits above the 55.6% break-even."""
    trader = _make_trader(session)
    _add_settled_losses(session, trader, 5, BASE_TS - 40_000)
    for i in range(9):
        decision_ts = BASE_TS - 20_000 + i * 600
        session.add(
            EventContractPaperBet(
                trader_id=trader.id,
                direction="long",
                status="settled",
                decision_time=_naive_utc(decision_ts),
                entry_time=_naive_utc(decision_ts),
                entry_price=100.0,
                expiry_time=_naive_utc(decision_ts + 300),
                expiry_price=101.0,
                result="win",
                pnl=80.0,
                stake=100.0,
                payout_ratio=0.8,
            )
        )
    session.commit()
    _add_due_losing_bet(session, trader, BASE_TS)

    _patch_market(monkeypatch, [_bar(BASE_TS, 99.0)])

    run_live_paper_cycle(now_ts=BASE_TS, db=session)

    session.refresh(trader)
    assert trader.enabled is True


def test_auto_pause_can_be_disabled_in_config(monkeypatch, session):
    trader = _make_trader(session, config=json.dumps({"auto_pause_enabled": False}))
    _add_settled_losses(session, trader, 13, BASE_TS - 20_000)
    _add_due_losing_bet(session, trader, BASE_TS)

    _patch_market(monkeypatch, [_bar(BASE_TS, 99.0)])

    run_live_paper_cycle(now_ts=BASE_TS, db=session)

    session.refresh(trader)
    assert trader.enabled is True


def test_auto_pause_skipped_while_bets_outstanding(monkeypatch, session):
    """With a pending_entry bet still outstanding after the settle phase, the
    sample is about to change; the pause check must wait for a clean state."""
    trader = _make_trader(session)
    _add_settled_losses(session, trader, 14, BASE_TS - 20_000)
    session.add(
        EventContractPaperBet(
            trader_id=trader.id,
            direction="long",
            status="pending_entry",
            decision_time=_naive_utc(BASE_TS + 600),  # no bar yet -> stays pending
            stake=100.0,
            payout_ratio=0.8,
        )
    )
    session.commit()

    _patch_market(monkeypatch, [_bar(BASE_TS - 60, 100.0)])

    run_live_paper_cycle(now_ts=BASE_TS, db=session)

    session.refresh(trader)
    assert trader.enabled is True
