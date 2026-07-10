"""L2 orderbook microstructure filters for signal_mode="range_boundary".

The boundary fade measured EXACTLY break-even (~55.3% over ~2000 trades vs
55.56% break-even), so the strategy doc prescribes exactly TWO L2 filters
(feature count capped at 2 to prevent overfitting):

1. range_require_obi — at a boundary touch the REVERSE-side depth skew must
   reach the threshold: long needs OBI = (bid5-ask5)/(bid5+ask5) >= +thr,
   short needs OBI <= -thr.
2. range_require_large_flow — recent aggressive large-order flow must agree
   with the bet: long needs large_buy_notional share >= thr over the trailing
   window, short needs the sell share >= thr.

Fail-closed contract: a set knob with missing/stale book or flow data BLOCKS
the trade (live-money filter — missing data must never silently pass).
Fingerprint contract: the knobs enter the normalized config ONLY when
explicitly provided, so existing strategies keep their fingerprints.
"""
from __future__ import annotations

import pytest

from services.event_contract_service import EventContractService
from services.event_contract_service import event_contract_service as svc

BASE = {"symbol": "BTC", "exchange": "binance", "period": "1m"}


def _features(**overrides):
    features = {"l2_obi": 0.35, "large_flow_buy_share": 0.70}
    features.update(overrides)
    return features


# --- OBI filter (pure helper) --------------------------------------------------


class TestObiFilter:
    CFG = {"range_require_obi": 0.30}

    def test_long_passes_with_strong_bid_skew(self):
        assert svc._l2_range_filters("long", _features(l2_obi=0.35), self.CFG) is None

    def test_long_blocked_on_weak_skew(self):
        reason = svc._l2_range_filters("long", _features(l2_obi=0.10), self.CFG)
        assert reason is not None and "深度倾斜" in reason

    def test_long_blocked_on_opposing_skew(self):
        reason = svc._l2_range_filters("long", _features(l2_obi=-0.2), self.CFG)
        assert reason is not None and "深度倾斜" in reason

    def test_long_threshold_is_inclusive(self):
        assert svc._l2_range_filters("long", _features(l2_obi=0.30), self.CFG) is None

    def test_short_passes_with_strong_ask_skew(self):
        assert svc._l2_range_filters("short", _features(l2_obi=-0.35), self.CFG) is None

    def test_short_blocked_on_weak_skew(self):
        reason = svc._l2_range_filters("short", _features(l2_obi=-0.10), self.CFG)
        assert reason is not None and "深度倾斜" in reason

    def test_short_blocked_on_opposing_skew(self):
        reason = svc._l2_range_filters("short", _features(l2_obi=0.2), self.CFG)
        assert reason is not None and "深度倾斜" in reason

    def test_short_threshold_is_inclusive(self):
        assert svc._l2_range_filters("short", _features(l2_obi=-0.30), self.CFG) is None


# --- Large-order flow alignment filter (pure helper) ---------------------------


class TestLargeFlowFilter:
    CFG = {"range_require_large_flow": 0.60}

    def test_long_passes_when_large_buyers_dominate(self):
        assert svc._l2_range_filters("long", _features(large_flow_buy_share=0.70), self.CFG) is None

    def test_long_blocked_when_buy_share_below_threshold(self):
        reason = svc._l2_range_filters("long", _features(large_flow_buy_share=0.55), self.CFG)
        assert reason is not None and "大单流向" in reason

    def test_long_threshold_is_inclusive(self):
        assert svc._l2_range_filters("long", _features(large_flow_buy_share=0.60), self.CFG) is None

    def test_short_passes_when_large_sellers_dominate(self):
        # buy share 0.25 -> sell share 0.75 >= 0.60
        assert svc._l2_range_filters("short", _features(large_flow_buy_share=0.25), self.CFG) is None

    def test_short_blocked_when_sell_share_below_threshold(self):
        # buy share 0.45 -> sell share 0.55 < 0.60
        reason = svc._l2_range_filters("short", _features(large_flow_buy_share=0.45), self.CFG)
        assert reason is not None and "大单流向" in reason

    def test_short_threshold_is_inclusive(self):
        assert svc._l2_range_filters("short", _features(large_flow_buy_share=0.40), self.CFG) is None


class TestBothFilters:
    CFG = {"range_require_obi": 0.30, "range_require_large_flow": 0.60}

    def test_both_pass(self):
        features = _features(l2_obi=0.4, large_flow_buy_share=0.75)
        assert svc._l2_range_filters("long", features, self.CFG) is None

    def test_obi_failure_reported_first(self):
        features = _features(l2_obi=0.1, large_flow_buy_share=0.75)
        reason = svc._l2_range_filters("long", features, self.CFG)
        assert reason is not None and "深度倾斜" in reason

    def test_flow_failure_reported_when_obi_passes(self):
        features = _features(l2_obi=0.4, large_flow_buy_share=0.50)
        reason = svc._l2_range_filters("long", features, self.CFG)
        assert reason is not None and "大单流向" in reason


# --- Fail-closed on missing data ------------------------------------------------


class TestMissingDataFailsClosed:
    def test_missing_obi_blocks_when_knob_set(self):
        reason = svc._l2_range_filters("long", {"large_flow_buy_share": 0.9}, {"range_require_obi": 0.30})
        assert reason is not None and "不可用" in reason

    def test_none_obi_blocks_when_knob_set(self):
        reason = svc._l2_range_filters("long", _features(l2_obi=None), {"range_require_obi": 0.30})
        assert reason is not None and "不可用" in reason

    def test_missing_large_flow_blocks_when_knob_set(self):
        reason = svc._l2_range_filters(
            "short", {"l2_obi": -0.9}, {"range_require_large_flow": 0.60}
        )
        assert reason is not None and "不可用" in reason

    def test_none_large_flow_blocks_when_knob_set(self):
        reason = svc._l2_range_filters(
            "short", _features(large_flow_buy_share=None), {"range_require_large_flow": 0.60}
        )
        assert reason is not None and "不可用" in reason


# --- Knobs absent -> no filtering at all ------------------------------------------


class TestKnobsAbsentNoFiltering:
    def test_hostile_features_pass_without_knobs(self):
        features = _features(l2_obi=-0.9, large_flow_buy_share=0.0)
        assert svc._l2_range_filters("long", features, {}) is None

    def test_missing_data_passes_without_knobs(self):
        assert svc._l2_range_filters("long", {}, {}) is None


# --- Config normalization / fingerprint stability --------------------------------


class TestConfigFingerprint:
    def test_knobs_absent_by_default(self):
        cfg = svc._normalize_config(dict(BASE), prediction=True)
        assert "range_require_obi" not in cfg
        assert "range_require_large_flow" not in cfg
        assert "range_require_obi" not in svc._public_config(cfg)
        assert "range_require_large_flow" not in svc._public_config(cfg)

    def test_fingerprint_stable_without_knobs(self):
        fp_a = svc._strategy_fingerprint(svc._normalize_config(dict(BASE), prediction=True))
        fp_b = svc._strategy_fingerprint(svc._normalize_config(dict(BASE), prediction=True))
        assert fp_a == fp_b

    def test_knobs_accepted_and_change_fingerprint(self):
        base = {**BASE, "signal_mode": "range_boundary"}
        cfg_plain = svc._normalize_config(dict(base), prediction=True)
        cfg_l2 = svc._normalize_config(
            {**base, "range_require_obi": 0.30, "range_require_large_flow": 0.60},
            prediction=True,
        )
        assert cfg_l2["range_require_obi"] == 0.30
        assert cfg_l2["range_require_large_flow"] == 0.60
        assert svc._strategy_fingerprint(cfg_plain) != svc._strategy_fingerprint(cfg_l2)

    def test_each_knob_forks_fingerprint_independently(self):
        base = {**BASE, "signal_mode": "range_boundary"}
        fp_plain = svc._strategy_fingerprint(svc._normalize_config(dict(base), prediction=True))
        fp_obi = svc._strategy_fingerprint(
            svc._normalize_config({**base, "range_require_obi": 0.30}, prediction=True)
        )
        fp_flow = svc._strategy_fingerprint(
            svc._normalize_config({**base, "range_require_large_flow": 0.60}, prediction=True)
        )
        assert len({fp_plain, fp_obi, fp_flow}) == 3


# --- Full dispatch through _analyze_snapshot --------------------------------------


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


# Passes every legacy quality gate AND the range_boundary structural gates
# (top-of-range touch), so only the L2 filters decide the outcome.
RANGE_TOP_FEATURES = {
    "fake_breakout_risk": 0.0,
    "trap_risk": 0.0,
    "bull_trap_risk": 0.0,
    "bear_trap_risk": 0.0,
    "range_risk": 0.0,
    "volume_ratio": 1.3,
    "mtf_conflict": False,
    "market_state": "range",
    "trend_score": 0.05,
    "rsi": 55.0,
    "exhaustion_long": False,
    "exhaustion_short": False,
    "range_pos": 0.92,
    "range_width_pct": 0.4,
    "atr_pct": 0.05,
    "ret60": 0.05,
}


@pytest.fixture()
def service():
    return EventContractService()


def _analyze(service, monkeypatch, cfg_extra, overrides=None):
    cfg = service._normalize_config(
        {**BASE, "decision_policy": "legacy_vote", "signal_mode": "range_boundary", **cfg_extra},
        prediction=True,
    )
    history = _history()
    features = service._compute_features(history)
    features.update(RANGE_TOP_FEATURES)
    features.update(overrides or {})
    monkeypatch.setattr(service, "_compute_features", lambda _history: features)
    return service._analyze_snapshot(history, cfg, decisions_override=_decisions("long"))


class TestRangeBoundaryDispatch:
    def test_knobs_absent_behavior_unchanged(self, service, monkeypatch):
        # No knobs: hostile/missing L2 data must not block (byte-identical to
        # the pre-filter engine).
        result = _analyze(
            service, monkeypatch, {}, overrides={"l2_obi": None, "large_flow_buy_share": None}
        )
        assert result["allow_trade"] is True
        assert result["final_direction"] == "short"
        assert not any("L2过滤" in reason for reason in result["blocked_reasons"])

    def test_passing_filters_allow_boundary_fade(self, service, monkeypatch):
        result = _analyze(
            service,
            monkeypatch,
            {"range_require_obi": 0.30, "range_require_large_flow": 0.60},
            overrides={"l2_obi": -0.40, "large_flow_buy_share": 0.25},
        )
        assert result["allow_trade"] is True
        assert result["final_direction"] == "short"

    def test_failing_obi_blocks_trade(self, service, monkeypatch):
        result = _analyze(
            service,
            monkeypatch,
            {"range_require_obi": 0.30},
            overrides={"l2_obi": 0.10, "large_flow_buy_share": 0.25},
        )
        assert result["allow_trade"] is False
        assert result["final_direction"] == "hold"
        assert result["signal_type"] == "hold_signal"
        assert any("L2过滤" in reason and "深度倾斜" in reason for reason in result["blocked_reasons"])

    def test_failing_large_flow_blocks_trade(self, service, monkeypatch):
        result = _analyze(
            service,
            monkeypatch,
            {"range_require_large_flow": 0.60},
            overrides={"l2_obi": -0.40, "large_flow_buy_share": 0.55},
        )
        assert result["allow_trade"] is False
        assert result["final_direction"] == "hold"
        assert any("L2过滤" in reason and "大单流向" in reason for reason in result["blocked_reasons"])

    def test_missing_l2_data_blocks_when_knob_set(self, service, monkeypatch):
        result = _analyze(
            service,
            monkeypatch,
            {"range_require_obi": 0.30},
            overrides={"l2_obi": None, "large_flow_buy_share": None},
        )
        assert result["allow_trade"] is False
        assert result["final_direction"] == "hold"
        assert any("不可用" in reason for reason in result["blocked_reasons"])


# --- Feature plumbing --------------------------------------------------------------


class TestComputeFeaturesExposure:
    def test_l2_obi_prefers_depth5(self, service):
        history = _history(80)
        history[-1]["l2"] = {
            "exchange": "binance",
            "bid_depth_5": 70.0,
            "ask_depth_5": 30.0,
            "bid_depth_10": 100.0,
            "ask_depth_10": 100.0,
            "imbalance_5": 0.4,
            "imbalance_10": 0.0,
        }
        features = service._compute_features(history)
        assert features["l2_obi"] == pytest.approx(0.4, abs=1e-9)

    def test_l2_obi_falls_back_to_depth10(self, service):
        history = _history(80)
        history[-1]["l2"] = {
            "exchange": "binance",
            "bid_depth_5": 0.0,
            "ask_depth_5": 0.0,
            "bid_depth_10": 30.0,
            "ask_depth_10": 70.0,
            "imbalance_5": 0.0,
            "imbalance_10": -0.4,
        }
        features = service._compute_features(history)
        assert features["l2_obi"] == pytest.approx(-0.4, abs=1e-9)

    def test_l2_obi_none_without_orderbook(self, service):
        # No real book -> None (the OHLCV-proxy orderbook_imbalance must NOT
        # leak into the fail-closed filter).
        features = service._compute_features(_history(80))
        assert features["l2_obi"] is None
        assert features["large_flow_buy_share"] is None

    def test_large_flow_share_comes_from_local_flow(self, service):
        history = _history(80)
        history[-1]["flow"] = {
            "source": "local_market_flow",
            "available_metrics": ["pair_taker_volume"],
            "cvd_delta_norm": 0.1,
            "taker_delta_norm": 0.1,
            "large_flow_buy_share": 0.7,
        }
        # CoinGlass priority for the shared flow fields must not hide the
        # local large-order share.
        history[-1]["coinglass"] = {
            "source": "coinglass",
            "available_metrics": ["funding_rate"],
            "funding_rate": 0.0001,
        }
        features = service._compute_features(history)
        assert features["large_flow_buy_share"] == pytest.approx(0.7)


class TestAttachFlowLargeOrders:
    def _bundle_and_klines(self):
        bar_ts = 1_751_000_000  # epoch seconds
        decision_ms = (bar_ts + 60) * 1000  # 1m bar close
        # (offset seconds before decision, buy_vol, sell_vol, large_buy, large_sell)
        records = [
            (120, 10.0, 10.0, 999_999.0, 0.0),  # outside the 60s window
            (30, 10.0, 10.0, 300.0, 100.0),
            (5, 10.0, 10.0, 100.0, 100.0),
            (-10, 10.0, 10.0, 0.0, 999_999.0),  # FUTURE row - must not leak
        ]
        taker_ts = [decision_ms - offset * 1000 for offset, *_ in records]
        buy_prefix = [0.0]
        sell_prefix = [0.0]
        large_buy_prefix = [0.0]
        large_sell_prefix = [0.0]
        for _, buy, sell, large_buy, large_sell in records:
            buy_prefix.append(buy_prefix[-1] + buy)
            sell_prefix.append(sell_prefix[-1] + sell)
            large_buy_prefix.append(large_buy_prefix[-1] + large_buy)
            large_sell_prefix.append(large_sell_prefix[-1] + large_sell)
        bundle = {
            "enabled": True,
            "taker_exchange": "binance",
            "taker_ts": taker_ts,
            "buy_prefix": buy_prefix,
            "sell_prefix": sell_prefix,
            "large_buy_prefix": large_buy_prefix,
            "large_sell_prefix": large_sell_prefix,
            "metric_ts": [],
            "metrics": [],
        }
        klines = [{**_bar(100.0), "timestamp": bar_ts}]
        return bundle, klines

    def test_trailing_window_share_is_leakage_free(self, service):
        bundle, klines = self._bundle_and_klines()
        cfg = {"period": "1m", "max_flow_lag_seconds": 60}
        out = service._attach_flow_features(klines, bundle, cfg)
        flow = out[0]["flow"]
        # Only the -30s and -5s rows count: (300+100)/(300+100+100+100) = 2/3.
        # The 999999 rows (outside window / in the future) must be excluded.
        assert flow["large_flow_buy_share"] == pytest.approx(2 / 3, abs=1e-9)

    def test_no_large_fields_when_bundle_lacks_them(self, service):
        bundle, klines = self._bundle_and_klines()
        bundle.pop("large_buy_prefix")
        bundle.pop("large_sell_prefix")
        cfg = {"period": "1m", "max_flow_lag_seconds": 60}
        out = service._attach_flow_features(klines, bundle, cfg)
        assert "large_flow_buy_share" not in out[0]["flow"]


class TestFlowVenueFallback:
    """The taker-row venue fallback must prefer venues whose large-order
    fields are POPULATED: hibt writes zeros forever, hyperliquid writes real
    values, and picking by raw row count alone selected the useless venue."""

    def test_fallback_prefers_venue_with_large_order_data(self):
        import datetime as dt

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from database.connection import Base
        from database.models import MarketTradesAggregated
        from services.event_contract_service import event_contract_service as svc

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[MarketTradesAggregated.__table__])
        db = sessionmaker(bind=engine)()
        base_ms = 1_783_600_000_000
        # hibt: MORE rows but zero large fields; hyperliquid: fewer rows, real large data.
        for i in range(20):
            db.add(MarketTradesAggregated(
                exchange="hibt", symbol="BTC", timestamp=base_ms + i * 15_000,
                taker_buy_volume=1, taker_sell_volume=1,
                large_buy_notional=0, large_sell_notional=0,
            ))
        for i in range(10):
            db.add(MarketTradesAggregated(
                exchange="hyperliquid", symbol="BTC", timestamp=base_ms + i * 15_000,
                taker_buy_volume=1, taker_sell_volume=1,
                large_buy_notional=50_000, large_sell_notional=30_000,
            ))
        db.commit()

        cfg = {"symbol": "BTC", "exchange": "binance"}
        rows, venue = svc._load_flow_taker_rows(db, cfg, base_ms - 1, base_ms + 10_000_000)
        assert venue == "hyperliquid"
        assert len(rows) == 10
        db.close()
