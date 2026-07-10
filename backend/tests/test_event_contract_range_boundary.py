"""signal_mode="range_boundary" — the Tier-2 box-boundary strategy.

用户策略文档第二梯队：只在价格进入明确震荡区间后交易——触碰上沿押跌、
触碰下沿押涨、区间中部绝对不进场，趋势过强时停用。方向由区间结构决定
（消费动量共识但不跟随它），与衰竭反打共用"翻转"机制但条件是结构性的。
Design thresholds are a-priori (no tuning against history); the declared
validation windows judge the mode.
"""
from __future__ import annotations

from services.event_contract_service import event_contract_service as svc


def _features(**overrides):
    features = {
        "range_pos": 0.5,
        "range_width_pct": 0.4,
        "atr_pct": 0.05,
        "ret60": 0.05,
        "rsi": 55.0,
    }
    features.update(overrides)
    return features


class TestRangeBoundaryVerdict:
    def test_top_of_range_reverts_short(self):
        direction, reason = svc._range_boundary_verdict(_features(range_pos=0.92))
        assert direction == "short" and reason is None

    def test_bottom_of_range_reverts_long(self):
        direction, reason = svc._range_boundary_verdict(_features(range_pos=0.08))
        assert direction == "long" and reason is None

    def test_mid_range_is_forbidden_zone(self):
        direction, reason = svc._range_boundary_verdict(_features(range_pos=0.5))
        assert direction is None and "中部" in reason

    def test_narrow_range_rejected(self):
        direction, reason = svc._range_boundary_verdict(
            _features(range_pos=0.95, range_width_pct=0.05)
        )
        assert direction is None and "宽度" in reason

    def test_strong_hourly_trend_disables_mode(self):
        direction, reason = svc._range_boundary_verdict(
            _features(range_pos=0.95, ret60=0.55)
        )
        assert direction is None and "趋势" in reason


class TestConfig:
    def test_range_boundary_accepted_and_fingerprinted(self):
        base = {"symbol": "BTC", "exchange": "binance"}
        cfg = svc._normalize_config({**base, "signal_mode": "range_boundary"}, prediction=True)
        assert cfg["signal_mode"] == "range_boundary"
        fp_plain = svc._strategy_fingerprint(svc._normalize_config(dict(base), prediction=True))
        fp_range = svc._strategy_fingerprint(cfg)
        assert fp_plain != fp_range

    def test_plain_config_fingerprint_untouched(self):
        cfg = svc._normalize_config({"symbol": "BTC", "exchange": "binance"}, prediction=True)
        assert "signal_mode" not in cfg


class TestHonestReporting:
    """A structural flip must get the same honesty treatment as the
    exhaustion flip: reason text states the boundary reversal, and the
    vote-based probability is not reported as the bet's expected win rate."""

    def test_reason_summary_states_boundary_reversal(self):
        features = {
            "market_state": "range",
            "trend_score": 0.05,
            "volume_ratio": 1.2,
            "fake_breakout_risk": 10.0,
            "trap_risk": 20.0,
        }
        text = svc._build_reason_summary(
            features, "short", 20, [], 25, None, range_boundary_reversal=True
        )
        assert "区间" in text
        assert "获得 20/25 个评审投票。" not in text

    def test_event_signal_expected_win_rate_null_on_range_flip(self):
        cfg = {"symbol": "BTC", "period": "1m", "expiry_minutes": 5}
        latest = {"timestamp": 1_783_345_500, "close": 61710.8}
        consensus = {
            "decision_policy": "legacy_vote",
            "exhaustion_reversal": False,
            "range_boundary_reversal": True,
            "reason_summary": "x",
            "top_votes": 20,
            "reviewer_count": 25,
            "required_votes": 5,
            "signal_strength": 88.0,
            "consensus_rate": 80.0,
        }
        signal = svc._build_event_signal(
            cfg=cfg, latest=latest, final_direction="short", allow_trade=True,
            signal_type="trade_signal", confidence=88.0, signal_strength=88.0,
            probabilities={"long": 80.0, "short": 5.0},
            risks={"trap": 20.0, "fake_breakout": 10.0, "range": 70.0,
                   "bull_trap": 0.0, "bear_trap": 0.0},
            blocked_reasons=[], factors=[], ai_consensus=consensus,
        )
        assert signal["expected_win_rate"] is None
        assert signal["expected_win_rate_basis"] == "reversal_flip_unmodeled"


class TestTightenedFilters:
    """Config v2 knobs (declared from the 2043/2044 stratification, to be
    judged on the untouched 5/1-5/29 holdout): minimum trap risk (price truly
    pinned at the extreme) and minimum trend magnitude (real pressure into
    the boundary). Keys enter cfg only when explicitly provided."""

    def test_knobs_absent_by_default_and_fingerprint_stable(self):
        cfg = svc._normalize_config({"symbol": "BTC", "exchange": "binance"}, prediction=True)
        assert "range_min_trap_risk" not in cfg
        assert "range_min_trend_mag" not in cfg

    def test_knobs_accepted_and_change_fingerprint(self):
        base = {"symbol": "BTC", "exchange": "binance", "signal_mode": "range_boundary"}
        cfg_plain = svc._normalize_config(dict(base), prediction=True)
        cfg_tight = svc._normalize_config(
            {**base, "range_min_trap_risk": 30, "range_min_trend_mag": 0.05}, prediction=True
        )
        assert cfg_tight["range_min_trap_risk"] == 30.0
        assert cfg_tight["range_min_trend_mag"] == 0.05
        assert svc._strategy_fingerprint(cfg_plain) != svc._strategy_fingerprint(cfg_tight)

    def test_low_trap_blocked_when_knob_set(self):
        features = {"range_pos": 0.92, "range_width_pct": 0.4, "atr_pct": 0.05,
                    "ret60": 0.05, "trend_score": 0.08, "trap_risk": 10.0}
        direction, reason = svc._range_boundary_verdict(
            features, min_trap_risk=30.0, min_trend_mag=0.05
        )
        assert direction is None and "陷阱" in reason

    def test_weak_trend_blocked_when_knob_set(self):
        features = {"range_pos": 0.92, "range_width_pct": 0.4, "atr_pct": 0.05,
                    "ret60": 0.05, "trend_score": 0.01, "trap_risk": 45.0}
        direction, reason = svc._range_boundary_verdict(
            features, min_trap_risk=30.0, min_trend_mag=0.05
        )
        assert direction is None and "趋势" in reason

    def test_qualifying_boundary_passes_with_knobs(self):
        features = {"range_pos": 0.92, "range_width_pct": 0.4, "atr_pct": 0.05,
                    "ret60": 0.05, "trend_score": 0.08, "trap_risk": 45.0}
        direction, reason = svc._range_boundary_verdict(
            features, min_trap_risk=30.0, min_trend_mag=0.05
        )
        assert direction == "short" and reason is None
