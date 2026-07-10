"""TDD coverage for the paper trader's soft, recoverable risk controls.

Two guards run at the top of the decide phase (settle/fill are never paused):

1. Consecutive-loss cooldown: after ``cooldown_loss_streak`` settled losses in a
   row (default 4), new decisions are skipped for ``cooldown_minutes`` (default
   60) measured from the newest settled bet's expiry_time. A win resets the
   streak; the trader resumes automatically.
2. Daily loss stop: once today's (UTC) settled pnl reaches a loss of
   ``daily_loss_cap_pct`` percent of initial_balance (default 5.0) - or the
   absolute ``daily_loss_cap`` dollars when that is set - no new decisions for
   the rest of the UTC day.

Unlike auto-pause these are transient: no config mutation, no disabling.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from services.event_contract.live_paper_trader import run_live_paper_cycle
from services.event_contract_service import event_contract_service

BASE_TS = int(datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc).timestamp())
DAY_SECONDS = 86400


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
        name=overrides.pop("name", "risk-control-trader"),
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


def _add_settled_bet(db, trader, expiry_ts, result="loss", pnl=-100.0):
    db.add(
        EventContractPaperBet(
            trader_id=trader.id,
            direction="long",
            status="settled",
            decision_time=_naive_utc(expiry_ts - 300),
            entry_time=_naive_utc(expiry_ts - 300),
            entry_price=100.0,
            expiry_time=_naive_utc(expiry_ts),
            expiry_price=99.0 if result == "loss" else 101.0,
            result=result,
            pnl=pnl,
            stake=100.0,
            payout_ratio=0.8,
        )
    )
    db.commit()


def _add_loss_streak(db, trader, count, last_expiry_ts, pnl=-100.0, spacing=600):
    """count consecutive settled losses, the newest expiring at last_expiry_ts."""
    for i in range(count):
        _add_settled_bet(db, trader, last_expiry_ts - (count - 1 - i) * spacing, "loss", pnl)


def _patch_market(monkeypatch):
    """Klines mock: one closed 1m bar right before each cycle's now_ts, so the
    decide phase always has a fresh bar to act on. Returns the predict-call log."""

    def _klines(db, exchange, symbol, period, start_ts, end_ts, environment):
        return [_bar(end_ts - 60, 100.0)]

    monkeypatch.setattr(event_contract_service, "_load_klines", _klines)

    calls = []

    def _predict(db_arg, cfg):
        calls.append(cfg)
        return {"allow_trade": False, "best_action": "wait"}

    monkeypatch.setattr(event_contract_service, "predict", _predict)
    return calls


# ---------------------------------------------------------------------------
# Consecutive-loss cooldown
# ---------------------------------------------------------------------------


def test_loss_streak_cooldown_blocks_then_resumes(monkeypatch, session, caplog):
    """4 consecutive settled losses -> no predict call while the 60-minute
    cooldown (measured from the newest settled expiry) is running; once it
    elapses the trader decides again on its own."""
    trader = _make_trader(session)
    last_expiry = BASE_TS - 600
    _add_loss_streak(session, trader, 4, last_expiry)

    calls = _patch_market(monkeypatch)
    caplog.set_level(logging.INFO, logger="services.event_contract.live_paper_trader")

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert calls == []
    assert counters == {"settled": 0, "entries_filled": 0, "decisions": 0, "bets_opened": 0, "errors": 0}
    cooldown_logs = [r for r in caplog.records if r.levelno == logging.INFO and "cooldown" in r.message]
    assert len(cooldown_logs) == 1
    # Transient state: nothing stamped into config, trader stays enabled.
    session.refresh(trader)
    assert trader.enabled is True
    assert json.loads(trader.config) == {}

    # 60 minutes after the newest settlement the cooldown has expired.
    counters = run_live_paper_cycle(now_ts=last_expiry + 60 * 60 + 120, db=session)

    assert len(calls) == 1
    assert counters["decisions"] == 1
    assert counters["errors"] == 0


def test_three_losses_then_win_no_cooldown(monkeypatch, session):
    """A win resets the streak: 3 losses followed by a win must not cool down."""
    trader = _make_trader(session)
    _add_loss_streak(session, trader, 3, BASE_TS - 1200)
    _add_settled_bet(session, trader, BASE_TS - 600, result="win", pnl=80.0)

    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert len(calls) == 1
    assert counters["decisions"] == 1
    assert counters["errors"] == 0


def test_cooldown_knobs_are_configurable(monkeypatch, session):
    """cooldown_loss_streak=2 / cooldown_minutes=30 from the stored config: two
    losses trigger it, and it lifts 30 minutes after the newest settlement."""
    trader = _make_trader(
        session, config=json.dumps({"cooldown_loss_streak": 2, "cooldown_minutes": 30})
    )
    last_expiry = BASE_TS - 600
    _add_loss_streak(session, trader, 2, last_expiry)

    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)
    assert calls == []
    assert counters["decisions"] == 0
    assert counters["errors"] == 0

    counters = run_live_paper_cycle(now_ts=last_expiry + 30 * 60 + 120, db=session)
    assert len(calls) == 1
    assert counters["decisions"] == 1


def test_settle_phase_still_runs_during_cooldown(monkeypatch, session):
    """Cooldown only pauses NEW decisions: a due open bet must still settle."""
    trader = _make_trader(session)
    _add_loss_streak(session, trader, 4, BASE_TS - 1200)
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="open",
        decision_time=_naive_utc(BASE_TS - 300),
        entry_time=_naive_utc(BASE_TS - 300),
        entry_price=101.0,
        expiry_time=_naive_utc(BASE_TS - 60),
        stake=100.0,
        payout_ratio=0.8,
    )
    session.add(bet)
    session.commit()

    calls = _patch_market(monkeypatch)  # bar at now-60 == expiry_ts, open 100.0 < 101.0 -> long loss

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert counters["settled"] == 1
    assert counters["errors"] == 0
    assert calls == []
    session.refresh(bet)
    assert bet.status == "settled"


# ---------------------------------------------------------------------------
# Daily loss stop
# ---------------------------------------------------------------------------


def test_daily_loss_stop_blocks_for_rest_of_utc_day(monkeypatch, session):
    """Settled pnl today at -6% of initial_balance (>= 5% default cap) -> no new
    decisions until the UTC day rolls over. Only 3 losses, so the loss-streak
    cooldown (default 4) is NOT what blocks here."""
    trader = _make_trader(session)
    # -600 total on a 10_000 initial balance = -6%.
    _add_loss_streak(session, trader, 3, BASE_TS - 4 * 3600, pnl=-200.0)

    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)
    assert calls == []
    assert counters["decisions"] == 0
    assert counters["errors"] == 0
    session.refresh(trader)
    assert trader.enabled is True
    assert json.loads(trader.config) == {}

    # Next UTC day: the daily ledger is empty again, trading resumes.
    counters = run_live_paper_cycle(now_ts=BASE_TS + DAY_SECONDS, db=session)
    assert len(calls) == 1
    assert counters["decisions"] == 1


def test_daily_loss_stop_ignores_yesterdays_losses(monkeypatch, session):
    """The same -6% worth of losses settled YESTERDAY must not stop today."""
    trader = _make_trader(session)
    _add_loss_streak(session, trader, 3, BASE_TS - DAY_SECONDS, pnl=-200.0)

    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert len(calls) == 1
    assert counters["decisions"] == 1
    assert counters["errors"] == 0


def test_daily_loss_stop_pct_knob_and_below_cap(monkeypatch, session):
    """daily_loss_cap_pct=10 raises the bar: -600 on 10_000 (-6%) no longer stops."""
    trader = _make_trader(session, config=json.dumps({"daily_loss_cap_pct": 10.0}))
    _add_loss_streak(session, trader, 3, BASE_TS - 4 * 3600, pnl=-200.0)

    calls = _patch_market(monkeypatch)

    run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert len(calls) == 1


def test_absolute_daily_loss_cap_takes_precedence(monkeypatch, session):
    """When the absolute daily_loss_cap is set it wins over the percent knob -
    in both directions."""
    # Absolute cap far above today's -600 loss: percent (5% = 500) would stop,
    # the absolute cap must not.
    lenient = _make_trader(session, name="lenient", config=json.dumps({"daily_loss_cap": 5000}))
    _add_loss_streak(session, lenient, 3, BASE_TS - 4 * 3600, pnl=-200.0)

    # Absolute cap of 100 with only -150 lost today: percent (500) would allow,
    # the absolute cap must stop.
    strict = _make_trader(
        session, name="strict", symbol="ETH", config=json.dumps({"daily_loss_cap": 100})
    )
    _add_loss_streak(session, strict, 3, BASE_TS - 4 * 3600, pnl=-50.0)

    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=BASE_TS, db=session)

    assert counters["errors"] == 0
    assert counters["decisions"] == 1
    assert len(calls) == 1
    assert calls[0]["symbol"] == "BTC"  # only the lenient trader decided
