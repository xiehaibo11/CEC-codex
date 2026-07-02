"""TDD coverage for the live event-contract paper trading cycle (spec module 1:
settle -> fill entry -> decide, non-overlapping, predict failures are isolated)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
import services.event_contract.live_paper_trader as live_paper_trader
from services.event_contract.live_paper_trader import run_live_paper_cycle
from services.event_contract_service import event_contract_service


@pytest.fixture(autouse=True)
def _reset_warned_bet_ids():
    """The warn-once tracker is module-level state; keep tests isolated."""
    live_paper_trader._WARNED_BET_IDS.clear()
    yield
    live_paper_trader._WARNED_BET_IDS.clear()

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
        name=overrides.pop("name", "run-850-clone"),
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


def _closed_bars_up_to(last_open_ts, count=5, base_price=100.0):
    """count consecutive 1m bars, last one opening at last_open_ts."""
    return [_bar(last_open_ts - 60 * i, base_price + (count - 1 - i)) for i in range(count - 1, -1, -1)]


def _allow_long_result(**overrides):
    result = {
        "allow_trade": True,
        "best_action": "long",
        "market_state": "trend_up",
        "signal_strength": 70.0,
        "reason": "test long signal",
        "similar_patterns": [{"noise": True}],
        "data_quality": {"warnings": []},
    }
    result.update(overrides)
    return result


def test_first_cycle_opens_pending_entry_bet(monkeypatch, session):
    trader = _make_trader(session)
    klines = _closed_bars_up_to(BASE_TS - 60)  # last closed bar: open=BASE_TS-60, close-time=BASE_TS
    now_ts = BASE_TS + 15

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)
    monkeypatch.setattr(event_contract_service, "predict", lambda db_arg, cfg: _allow_long_result())

    counters = run_live_paper_cycle(now_ts=now_ts, db=session)

    assert counters == {"settled": 0, "entries_filled": 0, "decisions": 1, "bets_opened": 1, "errors": 0}

    bets = session.query(EventContractPaperBet).filter_by(trader_id=trader.id).all()
    assert len(bets) == 1
    bet = bets[0]
    assert bet.status == "pending_entry"
    assert bet.direction == "long"
    assert bet.stake == 100.0
    assert bet.payout_ratio == 0.8
    assert bet.decision_time == _naive_utc(BASE_TS)
    snapshot = json.loads(bet.analysis_snapshot)
    assert "similar_patterns" not in snapshot
    assert "data_quality" not in snapshot


def test_next_bar_fills_entry_at_its_open(monkeypatch, session):
    trader = _make_trader(session)
    decision_ts = BASE_TS
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="pending_entry",
        decision_time=_naive_utc(decision_ts),
        stake=100.0,
        payout_ratio=0.8,
    )
    session.add(bet)
    session.commit()

    entry_bar = _bar(decision_ts, 12345.6)
    klines = [entry_bar]
    now_ts = decision_ts + 30

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)

    def _fail_predict(*a, **k):
        raise AssertionError("predict must not be called while a bet is outstanding")

    monkeypatch.setattr(event_contract_service, "predict", _fail_predict)

    counters = run_live_paper_cycle(now_ts=now_ts, db=session)

    assert counters == {"settled": 0, "entries_filled": 1, "decisions": 0, "bets_opened": 0, "errors": 0}

    session.refresh(bet)
    assert bet.status == "open"
    assert bet.entry_price == 12345.6
    assert bet.entry_time == _naive_utc(decision_ts)
    assert bet.expiry_time == _naive_utc(decision_ts + 5 * 60)


def test_expiry_settles_win_and_updates_balance(monkeypatch, session):
    trader = _make_trader(session, current_balance=10000.0)
    expiry_ts = BASE_TS
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="open",
        decision_time=_naive_utc(expiry_ts - 5 * 60),
        entry_time=_naive_utc(expiry_ts - 5 * 60),
        entry_price=100.0,
        expiry_time=_naive_utc(expiry_ts),
        stake=100.0,
        payout_ratio=0.8,
    )
    session.add(bet)
    session.commit()

    expiry_bar = _bar(expiry_ts, 110.0)  # long, expiry open > entry -> win
    klines = [expiry_bar]
    now_ts = expiry_ts  # the expiry bar itself hasn't closed yet -> decide phase can't fire

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)

    def _fail_predict(*a, **k):
        raise AssertionError("predict must not be called in this test")

    monkeypatch.setattr(event_contract_service, "predict", _fail_predict)

    counters = run_live_paper_cycle(now_ts=now_ts, db=session)

    assert counters == {"settled": 1, "entries_filled": 0, "decisions": 0, "bets_opened": 0, "errors": 0}

    session.refresh(bet)
    assert bet.status == "settled"
    assert bet.result == "win"
    assert bet.expiry_price == 110.0
    assert bet.pnl == pytest.approx(100.0 * 0.8)  # fee_rate defaults to 0

    session.refresh(trader)
    assert trader.current_balance == pytest.approx(10000.0 + 80.0)


def test_open_bet_blocks_new_decisions(monkeypatch, session):
    trader = _make_trader(session)
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="open",
        decision_time=_naive_utc(BASE_TS - 3600),
        entry_time=_naive_utc(BASE_TS - 3600),
        entry_price=100.0,
        expiry_time=_naive_utc(BASE_TS + 3600),  # not due yet
        stake=100.0,
        payout_ratio=0.8,
    )
    session.add(bet)
    session.commit()

    klines = _closed_bars_up_to(BASE_TS - 60)
    now_ts = BASE_TS + 15

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)

    def _fail_predict(*a, **k):
        raise AssertionError("predict must not be called while a bet is outstanding")

    monkeypatch.setattr(event_contract_service, "predict", _fail_predict)

    counters = run_live_paper_cycle(now_ts=now_ts, db=session)

    assert counters == {"settled": 0, "entries_filled": 0, "decisions": 0, "bets_opened": 0, "errors": 0}
    bets = session.query(EventContractPaperBet).filter_by(trader_id=trader.id).all()
    assert len(bets) == 1
    assert bets[0].status == "open"


def test_predict_exception_is_isolated_per_trader(monkeypatch, session):
    broken_trader = _make_trader(
        session, name="broken-trader", config=json.dumps({"_raise": True})
    )
    healthy_trader = _make_trader(session, name="healthy-trader")

    klines = _closed_bars_up_to(BASE_TS - 60)
    now_ts = BASE_TS + 15

    def fake_predict(db_arg, cfg):
        if cfg.get("_raise"):
            raise RuntimeError("boom")
        return _allow_long_result()

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)
    monkeypatch.setattr(event_contract_service, "predict", fake_predict)

    counters = run_live_paper_cycle(now_ts=now_ts, db=session)

    assert counters == {"settled": 0, "entries_filled": 0, "decisions": 1, "bets_opened": 1, "errors": 1}

    broken_bets = session.query(EventContractPaperBet).filter_by(trader_id=broken_trader.id).all()
    healthy_bets = session.query(EventContractPaperBet).filter_by(trader_id=healthy_trader.id).all()
    assert broken_bets == []
    assert len(healthy_bets) == 1
    assert healthy_bets[0].status == "pending_entry"


def test_predict_exception_rolls_back_session(monkeypatch, session):
    """Regression for the aborted-transaction bug: on Postgres a failed statement
    poisons the shared session for every subsequent trader in the cycle
    (InFailedSqlTransaction) unless it's rolled back immediately. SQLite has no
    equivalent failure mode, so this test can only assert the contract - that
    live_paper_trader always calls session.rollback() right after a predict
    failure - via a spy wrapper, not reproduce the actual Postgres poisoning.
    """
    _make_trader(session, name="broken-trader")
    klines = _closed_bars_up_to(BASE_TS - 60)
    now_ts = BASE_TS + 15

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)

    def _raise_predict(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(event_contract_service, "predict", _raise_predict)

    rollback_calls = []
    original_rollback = session.rollback

    def _rollback_spy():
        rollback_calls.append(True)
        return original_rollback()

    monkeypatch.setattr(session, "rollback", _rollback_spy)

    counters = run_live_paper_cycle(now_ts=now_ts, db=session)

    assert counters["errors"] == 1
    assert len(rollback_calls) == 1


def test_missing_expiry_bar_warns_once_per_bet(monkeypatch, session, caplog):
    trader = _make_trader(session)
    expiry_ts = BASE_TS
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="open",
        decision_time=_naive_utc(expiry_ts - 5 * 60),
        entry_time=_naive_utc(expiry_ts - 5 * 60),
        entry_price=100.0,
        expiry_time=_naive_utc(expiry_ts),
        stake=100.0,
        payout_ratio=0.8,
    )
    session.add(bet)
    session.commit()

    # No bar at or after expiry_ts -> _resolve_expiry_index returns (None, None) on
    # every cycle, and now_ts is far enough past expiry to exceed the default
    # max_expiry_lag_seconds (60s for the 1m period) both times.
    klines = _closed_bars_up_to(BASE_TS - 3600)
    now_ts = expiry_ts + 10_000

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)

    def _fail_predict(*a, **k):
        raise AssertionError("predict must not be called while a bet is outstanding")

    monkeypatch.setattr(event_contract_service, "predict", _fail_predict)

    caplog.set_level(logging.WARNING, logger="services.event_contract.live_paper_trader")

    run_live_paper_cycle(now_ts=now_ts, db=session)
    run_live_paper_cycle(now_ts=now_ts + 60, db=session)

    warnings = [r for r in caplog.records if "no expiry bar" in r.message]
    assert len(warnings) == 1


def test_fill_pending_entry_applies_slippage(monkeypatch, session):
    trader = _make_trader(session, config=json.dumps({"slippage_bps": 100}))
    decision_ts = BASE_TS
    bet = EventContractPaperBet(
        trader_id=trader.id,
        direction="long",
        status="pending_entry",
        decision_time=_naive_utc(decision_ts),
        stake=100.0,
        payout_ratio=0.8,
    )
    session.add(bet)
    session.commit()

    bar_open = 12345.6
    entry_bar = _bar(decision_ts, bar_open)
    klines = [entry_bar]
    now_ts = decision_ts + 30

    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)

    def _fail_predict(*a, **k):
        raise AssertionError("predict must not be called while a bet is outstanding")

    monkeypatch.setattr(event_contract_service, "predict", _fail_predict)

    counters = run_live_paper_cycle(now_ts=now_ts, db=session)

    assert counters["entries_filled"] == 1
    session.refresh(bet)
    assert bet.status == "open"
    assert bet.entry_price == pytest.approx(bar_open * 1.01)
