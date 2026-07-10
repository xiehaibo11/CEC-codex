"""Wiring test: predict() must consult the historical EV gate before
allowing a trade, and must report the historical estimate as the signal's
expected win rate (basis: historical_similar_trades).

The gate knobs live in the RAW config (never in the normalized cfg), so
enabling/disabling the gate cannot change a strategy fingerprint.
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
from services.event_contract_service import event_contract_service

BASE_TS = int(dt.datetime(2026, 7, 2, 12, 0, 0, tzinfo=dt.timezone.utc).timestamp())


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[EventContractBacktestRun.__table__, EventContractTradeLog.__table__],
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _bar(ts, price):
    return {
        "timestamp": ts,
        "open": price,
        "high": price + 0.5,
        "low": price - 0.5,
        "close": price,
        "volume": 10.0,
    }


def _canned_analysis(**overrides):
    ai_consensus = {
        "allow_trade": True,
        "exhaustion_reversal": True,
        "reason_summary": "canned",
        "decision_policy": "legacy_vote",
        "top_votes": 25,
        "reviewer_count": 25,
        "required_votes": 5,
        "signal_strength": 91.0,
        "consensus_rate": 100.0,
    }
    analysis = {
        "decision_policy": "legacy_vote",
        "ai_participated": False,
        "ai_model": None,
        "ai_account_name": None,
        "market_state": "breakout",
        "long_probability": 85.0,
        "short_probability": 1.0,
        "hold_probability": 14.0,
        "final_direction": "short",
        "allow_trade": True,
        "confidence": 90.0,
        "signal_strength": 91.0,
        "signal_type": "trade_signal",
        "event_signal_type": "SHORT_5M_EVENT",
        "trap_risk": 40.0,
        "fake_breakout_risk": 0.0,
        "range_risk": 0.0,
        "edge_score": 100.0,
        "risk_score": 44.0,
        "execution_score": 99.0,
        "decision_grade": "A",
        "trade_readiness": "tradable",
        "veto_reasons": [],
        "decision_diagnostics": {},
        "reason_summary": "canned",
        "blocked_reasons": [],
        "ai_consensus": ai_consensus,
        "ai_decisions": [],
        "factors": [],
        "event_signal": {
            "direction": "short",
            "expected_win_rate": None,
            "expected_win_rate_basis": "reversal_flip_unmodeled",
            "veto_reasons": [],
            "ai_consensus": ai_consensus,
        },
    }
    analysis.update(overrides)
    return analysis


@pytest.fixture()
def patched_predict(monkeypatch):
    klines = [_bar(BASE_TS - 60 * i, 100.0) for i in range(120, 0, -1)]
    monkeypatch.setattr(event_contract_service, "_load_klines", lambda *a, **k: klines)
    monkeypatch.setattr(event_contract_service, "_load_reviewer_weights", lambda *a, **k: {})
    monkeypatch.setattr(
        event_contract_service, "_load_l2_feature_bundle", lambda *a, **k: {"enabled": False}
    )
    monkeypatch.setattr(
        event_contract_service, "_load_flow_feature_bundle", lambda *a, **k: {"enabled": False}
    )
    monkeypatch.setattr(
        event_contract_service,
        "_load_coinglass_feature_bundle",
        lambda *a, **k: {"enabled": False},
    )
    monkeypatch.setattr(
        event_contract_service, "_analyze_snapshot", lambda *a, **k: _canned_analysis()
    )
    monkeypatch.setattr(
        event_contract_service, "_find_similar_patterns", lambda *a, **k: []
    )
    return klines


def _seed_history(db, wins, losses, market_state="breakout"):
    run = EventContractBacktestRun(
        symbol="BTC", exchange="binance", environment="mainnet", period="1m",
        start_time=dt.datetime(2026, 5, 1), end_time=dt.datetime(2026, 7, 1),
        status="completed",
    )
    db.add(run)
    db.commit()
    base = dt.datetime(2026, 6, 1)
    for i in range(wins + losses):
        result = "win" if i < wins else "loss"
        db.add(
            EventContractTradeLog(
                run_id=run.id,
                trade_index=i,
                symbol="BTC",
                direction="short",
                entry_time=base + dt.timedelta(minutes=10 * i),
                entry_price=100.0,
                expiry_time=base + dt.timedelta(minutes=10 * i + 5),
                expiry_price=99.0,
                result=result,
                profit_loss=80.0 if result == "win" else -100.0,
                market_state=market_state,
            )
        )
    db.commit()


def test_predict_blocks_trade_without_demonstrated_edge(session, patched_predict):
    # 47/100 historical - the real family's profile. Signal fires, gate blocks.
    _seed_history(session, 47, 53)
    result = event_contract_service.predict(session, {"symbol": "BTC", "exchange": "binance"})

    assert result["best_action"] == "short"
    assert result["allow_trade"] is False
    assert any("EV门" in reason for reason in result["veto_reasons"])
    assert result["historical_ev"]["n"] == 100
    assert result["event_signal"]["expected_win_rate"] == pytest.approx(47.0)
    assert result["event_signal"]["expected_win_rate_basis"] == "historical_similar_trades"


def test_predict_allows_trade_with_demonstrated_edge(session, patched_predict):
    # 130/180 = 72.2%, Wilson lower bound ~65% clears break-even.
    _seed_history(session, 130, 50)
    result = event_contract_service.predict(session, {"symbol": "BTC", "exchange": "binance"})

    assert result["allow_trade"] is True
    assert result["historical_ev"]["n"] == 180
    assert result["event_signal"]["expected_win_rate"] == pytest.approx(72.22)
    assert result["event_signal"]["expected_win_rate_basis"] == "historical_similar_trades"


def test_ev_gate_can_be_disabled_in_raw_config(session, patched_predict):
    result = event_contract_service.predict(
        session, {"symbol": "BTC", "exchange": "binance", "enable_ev_gate": False}
    )
    assert result["allow_trade"] is True
    assert "historical_ev" not in result


def test_ev_gate_knobs_do_not_change_fingerprint():
    base = {"symbol": "BTC", "exchange": "binance"}
    with_gate = {**base, "enable_ev_gate": False, "ev_gate_min_n": 100}
    fp_base = event_contract_service._strategy_fingerprint(
        event_contract_service._normalize_config(dict(base), prediction=True)
    )
    fp_gated = event_contract_service._strategy_fingerprint(
        event_contract_service._normalize_config(dict(with_gate), prediction=True)
    )
    assert fp_base == fp_gated
