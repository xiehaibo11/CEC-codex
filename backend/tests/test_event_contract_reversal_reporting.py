"""Exhaustion-reversal flips must be reported honestly.

Live bug: after the exhaustion gate flipped a 25/25-LONG momentum consensus
into a SHORT bet, the persisted reason claimed 「做空，获得 25/25 个评审投票」,
entry_condition claimed 「25/25 票支持做空」, and event_signal carried
expected_win_rate=1 (the vote-based probability of the *flipped* direction,
which the strategy is deliberately betting against). Downstream calibration
already flagged it: predicted_avg 1.8 vs actual 67.8.
"""
from __future__ import annotations

from services.event_contract_service import event_contract_service

FEATURES = {
    "market_state": "breakout",
    "trend_score": 0.2344,
    "volume_ratio": 1.56,
    "fake_breakout_risk": 0.0,
    "trap_risk": 40.0,
}


def _reason(direction, exhaustion_reversal):
    return event_contract_service._build_reason_summary(
        FEATURES, direction, 25, [], 25, None, exhaustion_reversal=exhaustion_reversal
    )


def test_reason_summary_attributes_votes_to_momentum_direction_on_flip():
    text = _reason("short", exhaustion_reversal=True)
    # The 25 votes were for the momentum (long) side; the bet fades them.
    assert "做多" in text
    assert "反手" in text or "反转" in text
    assert "获得 25/25 个评审投票" not in text


def test_reason_summary_unchanged_without_flip():
    text = _reason("short", exhaustion_reversal=False)
    assert "获得 25/25 个评审投票" in text


def _event_signal(exhaustion_reversal):
    cfg = {"symbol": "BTC", "period": "1m", "expiry_minutes": 5}
    latest = {"timestamp": 1_783_345_500, "close": 61710.8}
    ai_consensus = {
        "decision_policy": "legacy_vote",
        "exhaustion_reversal": exhaustion_reversal,
        "reason_summary": "x",
        "top_votes": 25,
        "reviewer_count": 25,
        "required_votes": 5,
        "signal_strength": 91.07,
        "consensus_rate": 100.0,
    }
    return event_contract_service._build_event_signal(
        cfg=cfg,
        latest=latest,
        final_direction="short",
        allow_trade=True,
        signal_type="trade_signal",
        confidence=90.56,
        signal_strength=91.07,
        probabilities={"long": 85.06, "short": 1.0},
        risks={"trap": 40.0, "fake_breakout": 0.0, "range": 0.0, "bull_trap": 0.0, "bear_trap": 0.0},
        blocked_reasons=[],
        factors=[],
        ai_consensus=ai_consensus,
    )


def test_event_signal_expected_win_rate_is_null_after_flip():
    signal = _event_signal(exhaustion_reversal=True)
    # 1% was the vote-based probability of the direction the strategy is
    # deliberately fading - it is not a prediction of this bet's win rate.
    assert signal["expected_win_rate"] is None
    assert signal["expected_win_rate_basis"] == "reversal_flip_unmodeled"


def test_event_signal_expected_win_rate_kept_without_flip():
    signal = _event_signal(exhaustion_reversal=False)
    assert signal["expected_win_rate"] == 1.0


def test_entry_condition_states_fade_on_flip():
    signal = _event_signal(exhaustion_reversal=True)
    condition = signal["entry_condition"]
    assert "反手" in condition or "反打" in condition
    assert "支持做空" not in condition


def test_entry_condition_unchanged_without_flip():
    signal = _event_signal(exhaustion_reversal=False)
    assert "支持做空" in signal["entry_condition"]
