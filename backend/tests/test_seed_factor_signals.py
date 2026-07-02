"""Unit tests for backend/scripts/seed_factor_signals.py (spec module 5).

Covers the script's pure percentile/threshold helpers against fake
distributions (no DB), and the idempotent create/bind helpers against an
in-memory sqlite session (signal_definitions, signal_pools,
account_strategy_configs, factor_values tables)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.connection import Base  # noqa: E402
from database.models.factors import FactorValue  # noqa: E402
from database.models.signals import SignalDefinition, SignalPool  # noqa: E402
from database.models.trading import AccountStrategyConfig  # noqa: E402
from scripts.seed_factor_signals import (  # noqa: E402
    POOL_NAME,
    bind_pool_to_account,
    build_signal_specs,
    derive_depth_ratio_thresholds,
    derive_log_return_thresholds,
    fetch_factor_values,
    get_or_create_pool,
    get_or_create_signal,
    percentile_cont,
    seed,
)


# ============ Pure helpers: percentile_cont / threshold derivation ============

class TestPercentileCont:
    def test_matches_hand_computed_linear_interpolation(self):
        # n=5, p=0.05 -> rank=0.2 -> 10 + 0.2*(20-10) = 12.0
        values = [10, 20, 30, 40, 50]
        assert percentile_cont(values, 0.05) == pytest.approx(12.0)
        # p=0.95 -> rank=3.8 -> 40 + 0.8*(50-40) = 48.0
        assert percentile_cont(values, 0.95) == pytest.approx(48.0)

    def test_median_of_odd_length_list(self):
        assert percentile_cont([1, 2, 3, 4, 5], 0.5) == pytest.approx(3.0)

    def test_unsorted_input_is_sorted_internally(self):
        assert percentile_cont([50, 10, 30, 20, 40], 0.05) == pytest.approx(12.0)

    def test_single_value(self):
        assert percentile_cont([42.0], 0.5) == 42.0

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            percentile_cont([], 0.5)

    def test_out_of_range_pct_raises(self):
        with pytest.raises(ValueError):
            percentile_cont([1, 2, 3], 1.5)


class TestThresholdDerivation:
    def test_log_return_thresholds_from_fake_distribution(self):
        # n=5 -> p5 rank=0.2 -> 12.0; p95 rank=3.8 -> 48.0 (values scaled down to
        # look like log-return magnitudes)
        values = [v / 10000 for v in (10, 20, 30, 40, 50)]
        p5, p95 = derive_log_return_thresholds(values)
        assert p5 == pytest.approx(0.0012)
        assert p95 == pytest.approx(0.0048)

    def test_depth_ratio_thresholds_from_fake_distribution(self):
        # n=10 -> p10 rank=0.9 -> 1.9; p90 rank=8.1 -> 9.1
        values = list(range(1, 11))
        p10, p90 = derive_depth_ratio_thresholds(values)
        assert p10 == pytest.approx(1.9)
        assert p90 == pytest.approx(9.1)

    def test_rounding_is_applied(self):
        values = [0.0001234567, 0.0009876543, 0.005, 0.01, 0.02]
        p5, p95 = derive_log_return_thresholds(values)
        # 6 decimal places for LOG_RETURN_1-scale values
        assert p5 == round(p5, 6)
        assert p95 == round(p95, 6)


class TestBuildSignalSpecs:
    def test_builds_four_specs_with_canonical_metric_key(self):
        specs = build_signal_specs(-0.0048, 0.0059, 0.045, 7.315, time_window="1h")
        assert len(specs) == 4
        names = {s["signal_name"] for s in specs}
        assert names == {
            "LOG_RETURN_1 超跌反转",
            "LOG_RETURN_1 超涨反转",
            "DEPTH_RATIO 买盘失衡",
            "DEPTH_RATIO 卖盘失衡",
        }
        for spec in specs:
            cond = spec["trigger_condition"]
            # Canonical trigger_condition schema read by signal_detection_service
            # uses "metric", not "indicator" - see conditions.py: metric = condition.get("metric")
            assert "metric" in cond
            assert cond["metric"].startswith("factor:")
            assert cond["operator"] in ("<", ">")
            assert cond["time_window"] == "1h"
            assert isinstance(cond["threshold"], float)

    def test_directions_match_reversal_semantics(self):
        specs = build_signal_specs(-0.0048, 0.0059, 0.045, 7.315)
        by_name = {s["signal_name"]: s["trigger_condition"] for s in specs}
        assert by_name["LOG_RETURN_1 超跌反转"]["operator"] == "<"
        assert by_name["LOG_RETURN_1 超跌反转"]["threshold"] == -0.0048
        assert by_name["LOG_RETURN_1 超涨反转"]["operator"] == ">"
        assert by_name["LOG_RETURN_1 超涨反转"]["threshold"] == 0.0059
        assert by_name["DEPTH_RATIO 买盘失衡"]["operator"] == ">"
        assert by_name["DEPTH_RATIO 买盘失衡"]["threshold"] == 7.315
        assert by_name["DEPTH_RATIO 卖盘失衡"]["operator"] == "<"
        assert by_name["DEPTH_RATIO 卖盘失衡"]["threshold"] == 0.045


# ============ DB-backed helpers: sqlite session ============

@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            SignalDefinition.__table__,
            SignalPool.__table__,
            AccountStrategyConfig.__table__,
            FactorValue.__table__,
        ],
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _seed_factor_values(db, factor_name, symbol, exchange, period, timestamps_and_values):
    for ts, value in timestamps_and_values:
        db.add(
            FactorValue(
                exchange=exchange,
                symbol=symbol,
                period=period,
                factor_name=factor_name,
                factor_category="test",
                timestamp=ts,
                value=value,
            )
        )
    db.commit()


class TestFetchFactorValues:
    def test_filters_by_symbol_exchange_period_and_lookback(self, session):
        import time

        now = int(time.time())
        day = 86400
        _seed_factor_values(
            session, "LOG_RETURN_1", "BTC", "binance", "1h",
            [
                (now - 5 * day, 0.01),   # within 30d lookback
                (now - 40 * day, 0.99),  # outside lookback - must be excluded
            ],
        )
        # Different symbol/exchange/period - must be excluded
        _seed_factor_values(session, "LOG_RETURN_1", "ETH", "binance", "1h", [(now - day, 0.5)])
        _seed_factor_values(session, "LOG_RETURN_1", "BTC", "hyperliquid", "1h", [(now - day, 0.6)])
        _seed_factor_values(session, "LOG_RETURN_1", "BTC", "binance", "5m", [(now - day, 0.7)])

        values = fetch_factor_values(session, "LOG_RETURN_1", "BTC", "binance", 30, "1h")
        assert values == [0.01]

    def test_null_values_excluded(self, session):
        import time

        now = int(time.time())
        session.add(
            FactorValue(
                exchange="binance", symbol="BTC", period="1h", factor_name="DEPTH_RATIO",
                factor_category="test", timestamp=now, value=None,
            )
        )
        session.commit()
        values = fetch_factor_values(session, "DEPTH_RATIO", "BTC", "binance", 30, "1h")
        assert values == []


class TestGetOrCreateSignal:
    def test_creates_then_reuses_by_name(self, session):
        cond = {"metric": "factor:LOG_RETURN_1", "operator": "<", "threshold": -0.01, "time_window": "1h"}
        sid1, created1 = get_or_create_signal(session, "LOG_RETURN_1 超跌反转", "desc", cond, "binance")
        session.commit()
        assert created1 is True

        sid2, created2 = get_or_create_signal(session, "LOG_RETURN_1 超跌反转", "different desc", cond, "binance")
        session.commit()
        assert created2 is False
        assert sid2 == sid1

        count = session.query(SignalDefinition).filter(
            SignalDefinition.signal_name == "LOG_RETURN_1 超跌反转"
        ).count()
        assert count == 1

    def test_persists_trigger_condition_as_json_with_metric_key(self, session):
        cond = {"metric": "factor:DEPTH_RATIO", "operator": ">", "threshold": 7.0, "time_window": "1h"}
        sid, _ = get_or_create_signal(session, "DEPTH_RATIO 买盘失衡", None, cond, "binance")
        session.commit()
        row = session.query(SignalDefinition).filter(SignalDefinition.id == sid).one()
        stored = json.loads(row.trigger_condition)
        assert stored == cond


class TestGetOrCreatePool:
    def test_creates_then_reuses_by_name(self, session):
        pid1, created1 = get_or_create_pool(session, POOL_NAME, [1, 2, 3, 4], ["BTC"], "OR", "binance")
        session.commit()
        assert created1 is True

        pid2, created2 = get_or_create_pool(session, POOL_NAME, [1, 2, 3, 4], ["BTC"], "OR", "binance")
        session.commit()
        assert created2 is False
        assert pid2 == pid1

        count = session.query(SignalPool).filter(SignalPool.pool_name == POOL_NAME).count()
        assert count == 1


class TestBindPoolToAccount:
    def _make_account_config(self, session, **overrides):
        defaults = dict(
            account_id=3,
            price_threshold=1.0,
            trigger_interval=900,
            signal_pool_ids=None,
            enabled="true",
            scheduled_trigger_enabled=True,
            exchange="binance",
        )
        defaults.update(overrides)
        cfg = AccountStrategyConfig(**defaults)
        session.add(cfg)
        session.commit()
        return cfg

    def test_binds_and_preserves_other_fields(self, session):
        self._make_account_config(session)
        bound = bind_pool_to_account(session, 3, 1)
        session.commit()
        assert bound is True

        cfg = session.query(AccountStrategyConfig).filter(AccountStrategyConfig.account_id == 3).one()
        assert json.loads(cfg.signal_pool_ids) == [1]
        assert cfg.scheduled_trigger_enabled is True
        assert cfg.trigger_interval == 900
        assert cfg.exchange == "binance"

    def test_idempotent_second_bind_is_noop(self, session):
        self._make_account_config(session, signal_pool_ids=json.dumps([5]))
        bound1 = bind_pool_to_account(session, 3, 1)
        session.commit()
        assert bound1 is True

        bound2 = bind_pool_to_account(session, 3, 1)
        session.commit()
        assert bound2 is False

        cfg = session.query(AccountStrategyConfig).filter(AccountStrategyConfig.account_id == 3).one()
        assert sorted(json.loads(cfg.signal_pool_ids)) == [1, 5]

    def test_missing_account_raises(self, session):
        with pytest.raises(SystemExit):
            bind_pool_to_account(session, 999, 1)


class TestSeedIntegration:
    def _populate_factor_values(self, session):
        import time

        now = int(time.time())
        hour = 3600
        # 20 samples each, spread across the lookback window
        for i in range(20):
            session.add(FactorValue(
                exchange="binance", symbol="BTC", period="1h", factor_name="LOG_RETURN_1",
                factor_category="statistical", timestamp=now - i * hour, value=(i - 10) / 1000.0,
            ))
            session.add(FactorValue(
                exchange="binance", symbol="BTC", period="1h", factor_name="DEPTH_RATIO",
                factor_category="microstructure", timestamp=now - i * hour, value=float(i + 1),
            ))
        session.add(AccountStrategyConfig(
            account_id=3, price_threshold=1.0, trigger_interval=900,
            signal_pool_ids=None, enabled="true", scheduled_trigger_enabled=True,
            exchange="binance",
        ))
        session.commit()

    def test_second_run_creates_no_duplicates(self, session):
        self._populate_factor_values(session)

        summary1 = seed(session, symbol="BTC", exchange="binance", account_id=3, lookback_days=30)
        session.commit()
        assert all(s["created"] for s in summary1["signals"])
        assert summary1["pool"]["created"] is True
        assert summary1["bound"] is True

        summary2 = seed(session, symbol="BTC", exchange="binance", account_id=3, lookback_days=30)
        session.commit()
        assert all(not s["created"] for s in summary2["signals"])
        assert summary2["pool"]["created"] is False
        assert summary2["bound"] is False

        # Same ids across both runs
        ids1 = [s["id"] for s in summary1["signals"]]
        ids2 = [s["id"] for s in summary2["signals"]]
        assert ids1 == ids2
        assert summary1["pool"]["id"] == summary2["pool"]["id"]

        assert session.query(SignalDefinition).count() == 4
        assert session.query(SignalPool).count() == 1

        cfg = session.query(AccountStrategyConfig).filter(AccountStrategyConfig.account_id == 3).one()
        assert json.loads(cfg.signal_pool_ids) == [summary1["pool"]["id"]]
        assert cfg.scheduled_trigger_enabled is True  # preserved, not touched

    def test_raises_on_insufficient_samples(self, session):
        session.add(AccountStrategyConfig(
            account_id=3, price_threshold=1.0, trigger_interval=900,
            signal_pool_ids=None, enabled="true", scheduled_trigger_enabled=True,
            exchange="binance",
        ))
        session.commit()
        with pytest.raises(SystemExit):
            seed(session, symbol="BTC", exchange="binance", account_id=3, lookback_days=30)
