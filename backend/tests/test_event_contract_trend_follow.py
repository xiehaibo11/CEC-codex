"""Trend-follow signal mode (signal_mode="trend_follow").

Customer mandate for 5/10-minute event contracts: 只顺大趋势开单，坚决不逆势；
优先识别行情底部顺势做多、高位顺势做空. The legacy engine does the OPPOSITE
(exhaustion fade flips the momentum consensus); 6867 deduplicated historical
trades showed the fade family has no positive expectancy. trend_follow:
1. never flips final_direction away from the momentum consensus;
2. requires 60-minute trend agreement (long: ret60 > +0.10%, short: < -0.10%);
3. blocks overextended chases (long blocked at RSI > 70, short at RSI < 30).

Fingerprint constraint: signal_mode enters the normalized config ONLY when
explicitly requesting a non-default mode, so every existing strategy keeps its
fingerprint (rolling-validation / OOS-pair continuity depends on it).
"""
from __future__ import annotations

import pytest

from services.event_contract_service import EventContractService

BASE = {"symbol": "BTC", "exchange": "binance", "period": "1m"}


def _bar(close, volume=10.0):
    return {
        "open": close,
        "high": close * 1.0005,
        "low": close * 0.9995,
        "close": close,
        "volume": volume,
        "timestamp": 0,
    }


def _history(n=120, base=100.0):
    return [_bar(base) for _ in range(n)]


@pytest.fixture()
def svc():
    return EventContractService()


def _cfg(svc, **extra):
    return svc._normalize_config(
        {**BASE, "decision_policy": "legacy_vote", **extra}, prediction=True
    )


def _decisions(direction="long", n=24, confidence=90.0):
    return [
        {
            "ai_name": f"Reviewer {i}",
            "source": "rule",
            "direction": direction,
            "confidence": confidence,
            "reason": "test vote",
        }
        for i in range(n)
    ]


# Feature overrides that pass every legacy quality gate (fake breakout / trap /
# range / volume / MTF / edge quality), so only the mode-specific gates decide.
CLEAN_FEATURES = {
    "fake_breakout_risk": 0.0,
    "trap_risk": 0.0,
    "bull_trap_risk": 0.0,
    "bear_trap_risk": 0.0,
    "range_risk": 0.0,
    "volume_ratio": 1.3,
    "mtf_conflict": False,
    "market_state": "trend_up",
    "trend_score": 0.15,
    "rsi": 55.0,
    "exhaustion_long": False,
    "exhaustion_short": False,
}


def _analyze(svc, monkeypatch, cfg, overrides=None, direction="long"):
    history = _history()
    features = svc._compute_features(history)
    features.update(CLEAN_FEATURES)
    features.update(overrides or {})
    monkeypatch.setattr(svc, "_compute_features", lambda _history: features)
    return svc._analyze_snapshot(history, cfg, decisions_override=_decisions(direction))


# --- trend_follow through _analyze_snapshot ---------------------------------


def test_trend_follow_aligned_long_allowed_and_never_flipped(svc, monkeypatch):
    # exhaustion_long=True would flip the bet in fade mode; trend_follow must not.
    result = _analyze(
        svc,
        monkeypatch,
        _cfg(svc, signal_mode="trend_follow"),
        overrides={"ret60": 0.5, "exhaustion_long": True},
    )
    assert result["allow_trade"] is True
    assert result["final_direction"] == "long"
    assert result["signal_type"] == "trade_signal"
    assert result["exhaustion_reversal"] is False
    assert result["ai_consensus"]["exhaustion_reversal"] is False


def test_trend_follow_blocks_counter_trend_long(svc, monkeypatch):
    result = _analyze(
        svc,
        monkeypatch,
        _cfg(svc, signal_mode="trend_follow"),
        overrides={"ret60": -0.5},
    )
    assert result["allow_trade"] is False
    assert result["final_direction"] == "hold"
    assert result["signal_type"] == "hold_signal"
    reasons = " ".join(result["blocked_reasons"])
    assert "顺势" in reasons and "大趋势" in reasons


def test_trend_follow_blocks_overbought_chase(svc, monkeypatch):
    result = _analyze(
        svc,
        monkeypatch,
        _cfg(svc, signal_mode="trend_follow"),
        overrides={"ret60": 0.5, "rsi": 75.0},
    )
    assert result["allow_trade"] is False
    assert result["final_direction"] == "hold"
    assert result["signal_type"] == "hold_signal"
    reasons = " ".join(result["blocked_reasons"])
    assert "超买" in reasons or "回调" in reasons


def test_trend_follow_keeps_existing_quality_gates(svc, monkeypatch):
    # A perfect 60m alignment must not bypass the trap filter. (The legacy
    # gates demote to a non-trade watch signal in both modes; the contract
    # here is "no trade", so assert allow_trade/signal_type, not direction.)
    result = _analyze(
        svc,
        monkeypatch,
        _cfg(svc, signal_mode="trend_follow"),
        overrides={"ret60": 0.5, "trap_risk": 80.0},
    )
    assert result["allow_trade"] is False
    assert result["signal_type"] != "trade_signal"
    assert any("陷阱" in reason for reason in result["blocked_reasons"])


# --- pure helper -------------------------------------------------------------


def test_trend_follow_gate_helper_boundaries(svc):
    gate = svc._trend_follow_block_reason
    # Aligned + healthy RSI passes.
    assert gate("long", {"ret60": 0.5, "rsi": 55.0}) is None
    assert gate("short", {"ret60": -0.5, "rsi": 45.0}) is None
    # +0.10 is not strictly above the threshold: still counter-trend for longs.
    assert gate("long", {"ret60": 0.10, "rsi": 55.0}) is not None
    assert gate("short", {"ret60": -0.10, "rsi": 45.0}) is not None
    # Missing/zero ret60 (history shorter than 61 bars) blocks both sides.
    assert gate("long", {"rsi": 55.0}) is not None
    assert gate("short", {"rsi": 45.0}) is not None
    # Anti-chase: overextension in the bet direction only.
    assert gate("long", {"ret60": 0.5, "rsi": 70.1}) is not None
    assert gate("short", {"ret60": -0.5, "rsi": 29.9}) is not None
    assert gate("long", {"ret60": 0.5, "rsi": 29.0}) is None
    assert gate("short", {"ret60": -0.5, "rsi": 71.0}) is None


# --- exhaustion_fade default unchanged ---------------------------------------


def test_default_mode_blocks_momentum_without_exhaustion(svc, monkeypatch):
    result = _analyze(svc, monkeypatch, _cfg(svc), overrides={"ret60": 0.5})
    assert result["allow_trade"] is False
    assert result["final_direction"] == "hold"
    assert any("衰竭" in reason for reason in result["blocked_reasons"])


def test_default_mode_still_fades_exhaustion(svc, monkeypatch):
    result = _analyze(svc, monkeypatch, _cfg(svc), overrides={"exhaustion_long": True})
    assert result["allow_trade"] is True
    assert result["final_direction"] == "short"
    assert result["exhaustion_reversal"] is True


# --- ret60 feature ------------------------------------------------------------


def test_compute_features_exposes_ret60(svc):
    bars = [_bar(100.0) for _ in range(61)] + [_bar(101.0)]
    features = svc._compute_features(bars)
    assert features["ret60"] == pytest.approx(1.0, abs=1e-6)
    # Shorter than 61 bars: guarded to 0.0 (no trend evidence).
    assert svc._compute_features([_bar(100.0) for _ in range(30)])["ret60"] == 0.0


# --- fingerprint continuity ----------------------------------------------------


def test_fingerprint_unchanged_when_signal_mode_absent(svc):
    cfg = svc._normalize_config({"symbol": "BTC", "exchange": "binance"}, prediction=True)
    assert "signal_mode" not in cfg
    assert "signal_mode" not in svc._public_config(cfg)


def test_trend_follow_changes_fingerprint(svc):
    plain = svc._normalize_config({"symbol": "BTC", "exchange": "binance"}, prediction=True)
    trend = svc._normalize_config(
        {"symbol": "BTC", "exchange": "binance", "signal_mode": "trend_follow"},
        prediction=True,
    )
    assert trend["signal_mode"] == "trend_follow"
    assert svc._strategy_fingerprint(trend) != svc._strategy_fingerprint(plain)


def test_explicit_default_mode_keeps_fingerprint(svc):
    # Explicitly asking for the default must not fork the strategy identity:
    # behavior is byte-identical, so the fingerprint must be too.
    plain = svc._normalize_config({"symbol": "BTC", "exchange": "binance"}, prediction=True)
    fade = svc._normalize_config(
        {"symbol": "BTC", "exchange": "binance", "signal_mode": "exhaustion_fade"},
        prediction=True,
    )
    assert svc._strategy_fingerprint(fade) == svc._strategy_fingerprint(plain)


def test_invalid_signal_mode_raises(svc):
    with pytest.raises(ValueError, match="signal_mode"):
        svc._normalize_config({**BASE, "signal_mode": "momentum_chase"}, prediction=True)


# --- API request schema --------------------------------------------------------


def test_api_request_schema_carries_signal_mode():
    """PredictRequest is a whitelist — pydantic silently drops undeclared
    fields (how enable_factor_gate got stripped on its first deploy)."""
    from api.event_contract_routes import PredictRequest

    assert PredictRequest().model_dump()["signal_mode"] == "trend_follow"
    req = PredictRequest(signal_mode="trend_follow")
    assert req.model_dump()["signal_mode"] == "trend_follow"
