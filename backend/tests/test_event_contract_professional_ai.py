"""Structured professional AI analysis for production event contracts."""

from __future__ import annotations

import json

import pytest

from services.event_contract.professional_ai import (
    build_professional_ai_prompt,
    parse_professional_ai_response,
)
from services.event_contract_service import event_contract_service


SNAPSHOT = {
    "aligned_direction": "long",
    "conflict": False,
    "directions": {"4h": "long", "30m": "long", "15m": "long", "10m": "long", "5m": "long"},
    "timeframes": {
        period: {
            "status": "ready",
            "direction": "long",
            "return_pct": 0.2,
            "bar_count": 10,
            "ema_fast": 100.2,
            "ema_slow": 100.1,
            "rsi": 58.0,
            "atr_pct": 0.2,
            "bars": [{"timestamp": 0, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1}],
        }
        for period in ("4h", "30m", "15m", "10m", "5m")
    },
}


def test_prompt_contains_all_required_timeframes_and_execution_contract():
    prompt = build_professional_ai_prompt(
        snapshot=SNAPSHOT,
        rule_analysis={"final_direction": "long", "allow_trade": True, "confidence": 82},
        config={"symbol": "BTC", "expiry_minutes": 5},
    )

    for timeframe in ("4h", "30m", "15m", "10m", "5m"):
        assert timeframe in prompt
    assert "long|short|hold" in prompt
    assert "next" in prompt.lower()
    assert "future" in prompt.lower()
    assert "ema_fast" in prompt
    assert "rsi" in prompt
    assert "atr_pct" in prompt


def test_parser_accepts_structured_review():
    review = parse_professional_ai_response(
        json.dumps(
            {
                "direction": "long",
                "confidence": 86,
                "timeframe_analysis": {period: "aligned" for period in SNAPSHOT["directions"]},
                "risk_flags": [],
                "invalid_conditions": ["15m trend turns short"],
                "reason": "All required timeframes align.",
            }
        )
    )

    assert review["direction"] == "long"
    assert review["confidence"] == 86
    assert set(review["timeframe_analysis"]) == set(SNAPSHOT["directions"])


def test_parser_converts_invalid_direction_to_hold_and_requires_timeframes():
    with pytest.raises(ValueError, match="timeframe_analysis"):
        parse_professional_ai_response(
            json.dumps(
                {
                    "direction": "buy",
                    "confidence": 90,
                    "timeframe_analysis": {"5m": "aligned"},
                    "risk_flags": [],
                    "invalid_conditions": [],
                    "reason": "bad",
                }
            )
        )


def test_parser_rejects_non_json_without_fabricating_ai_result():
    with pytest.raises(ValueError, match="JSON"):
        parse_professional_ai_response("not an AI result")


def _gate_result():
    return {
        "best_action": "long",
        "allow_trade": True,
        "signal_type": "trade_signal",
        "event_signal_type": "LONG_5M_EVENT",
        "confidence": 90,
        "signal_strength": 92,
        "long_5m_probability": 82,
        "short_5m_probability": 12,
        "hold_probability": 6,
        "trap_risk": 10,
        "fake_breakout_risk": 10,
        "range_risk": 10,
        "veto_reasons": [],
        "entry_warning": "",
        "reason": "rule signal",
        "factors": [],
        "ai_consensus": {
            "decision_policy": "professional_v1",
            "reason_summary": "rule signal",
            "edge_score": 90,
            "edge_score_raw": 90,
            "risk_score": 10,
            "execution_score": 90,
            "decision_grade": "A",
            "trade_readiness": "tradable",
            "decision_diagnostics": {},
            "bull_trap_risk": 10,
            "bear_trap_risk": 10,
        },
    }


def _gate_cfg():
    return {
        "symbol": "BTC",
        "period": "1m",
        "expiry_minutes": 5,
        "professional_ai_min_confidence": 75,
        "_production_mtf_snapshot": {
            "aligned_direction": "long",
            "conflict": False,
        },
    }


def test_professional_ai_must_confirm_rule_direction():
    result = _gate_result()
    event_contract_service._apply_professional_ai_review(
        result=result,
        cfg=_gate_cfg(),
        latest={"timestamp": 1_000, "close": 100.0},
        review={
            "direction": "short",
            "confidence": 99,
            "timeframe_analysis": {period: "confirms" for period in ("4h", "30m", "15m", "10m", "5m")},
            "reason": "opposes rule",
        },
    )

    assert result["allow_trade"] is False
    assert result["best_action"] == "hold"
    assert result["event_signal_type"] == "HOLD"
    assert any("不一致" in item for item in result["veto_reasons"])


def test_professional_ai_failure_is_visible_hold():
    result = _gate_result()
    event_contract_service._apply_professional_ai_review(
        result=result,
        cfg=_gate_cfg(),
        latest={"timestamp": 1_000, "close": 100.0},
        review=None,
        error="provider unavailable",
    )

    assert result["allow_trade"] is False
    assert result["best_action"] == "hold"
    assert result["professional_ai_review"]["status"] == "unavailable"
    assert "provider unavailable" in result["entry_warning"]
