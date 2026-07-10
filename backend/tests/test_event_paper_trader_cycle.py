"""Production Paper Trader cadence and hard-stop behavior."""

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

NOW = int(datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc).timestamp())


def _dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)


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


def _trader(db, **overrides):
    values = {
        "name": "production-cycle",
        "enabled": True,
        "symbol": "BTC",
        "exchange": "binance",
        "environment": "mainnet",
        "config": "{}",
        "stake_amount": 100,
        "initial_balance": 10000,
        "current_balance": 10000,
    }
    values.update(overrides)
    trader = EventContractPaperTrader(**values)
    db.add(trader)
    db.commit()
    db.refresh(trader)
    return trader


def _bar(ts: int):
    return {
        "timestamp": ts,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 10.0,
    }


def _patch_market(monkeypatch, prediction=None):
    monkeypatch.setattr(
        event_contract_service,
        "_load_klines",
        lambda *args, **kwargs: [_bar(NOW - 60)],
    )
    calls = []

    def _predict(db, cfg):
        calls.append(cfg)
        return prediction or {"allow_trade": False, "best_action": "hold"}

    monkeypatch.setattr(event_contract_service, "predict", _predict)
    return calls


def _settled_bet(db, trader, index: int, result="win"):
    expiry = NOW - 60 - index * 60
    db.add(
        EventContractPaperBet(
            trader_id=trader.id,
            direction="long",
            status="settled",
            decision_time=_dt(expiry - 300),
            entry_time=_dt(expiry - 300),
            entry_price=100,
            expiry_time=_dt(expiry),
            expiry_price=101 if result == "win" else 99,
            result=result,
            pnl=80 if result == "win" else -100,
            stake=100,
            payout_ratio=0.8,
        )
    )


def test_same_closed_bar_is_evaluated_once_even_when_ai_holds(monkeypatch, session):
    trader = _trader(session)
    calls = _patch_market(monkeypatch)

    first = run_live_paper_cycle(now_ts=NOW, db=session)
    second = run_live_paper_cycle(now_ts=NOW, db=session)

    assert first["decisions"] == 1
    assert second["decisions"] == 0
    assert len(calls) == 1
    session.refresh(trader)
    assert trader.last_decision_time == _dt(NOW)


def test_eleventh_daily_decision_is_blocked(monkeypatch, session):
    trader = _trader(session)
    for index in range(10):
        _settled_bet(session, trader, index)
    session.commit()
    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=NOW, db=session)

    assert counters["decisions"] == 0
    assert calls == []


def test_equity_double_disables_new_entries(monkeypatch, session):
    trader = _trader(session, current_balance=20000)
    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=NOW, db=session)

    assert counters["decisions"] == 0
    assert calls == []
    session.refresh(trader)
    assert trader.enabled is False
    assert json.loads(trader.config)["profit_target"]["multiplier"] == 2


def test_legacy_countertrend_trader_is_disabled_without_a_decision(monkeypatch, session):
    trader = _trader(session, config=json.dumps({"signal_mode": "range_boundary"}))
    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=NOW, db=session)

    assert counters["decisions"] == 0
    assert calls == []
    session.refresh(trader)
    assert trader.enabled is False


def test_disabled_trader_still_settles_outstanding_bet(monkeypatch, session):
    trader = _trader(
        session,
        enabled=False,
        config=json.dumps({"signal_mode": "trend_follow"}),
    )
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="open",
        decision_time=_dt(NOW - 6 * 60),
        entry_time=_dt(NOW - 5 * 60),
        entry_price=99,
        expiry_time=_dt(NOW - 60),
        stake=100,
        payout_ratio=0.8,
    )
    session.add(bet)
    session.commit()
    calls = _patch_market(monkeypatch)

    counters = run_live_paper_cycle(now_ts=NOW, db=session)

    assert counters["settled"] == 1
    assert counters["decisions"] == 0
    assert calls == []
    session.refresh(bet)
    assert bet.status == "settled"
    assert bet.result == "win"
