"""Stratified validation of signal-trigger extremity vs settled outcomes.

Motivation: the only losing DEPTH_RATIO buy on the Binance testnet fired at an
extreme reading (31.2, ~4x threshold) right before a local top - extreme depth
imbalance may be absorption/spoofing rather than genuine demand. One sample
proves nothing, so the report is sample-gated: buckets report
``insufficient_sample`` until they hold enough settled trades to say anything.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.accounts_auth import Account
from database.models.trading import AIDecisionLog
from services.signal_trigger_validation import (
    parse_trigger_value,
    signal_trigger_stratified_report,
)

NOW = dt.datetime(2026, 7, 7, 12, 0, 0)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Account.__table__, AIDecisionLog.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    account = Account(user_id=1, name="strat-test", account_type="AI", is_active="true")
    db.add(account)
    db.commit()
    db.info["account_id"] = account.id
    try:
        yield db
    finally:
        db.close()


def _add(db, reason, pnl, minutes_ago=60, operation="buy"):
    db.add(
        AIDecisionLog(
            account_id=db.info["account_id"],
            decision_time=NOW - dt.timedelta(minutes=minutes_ago),
            reason=reason,
            operation=operation,
            symbol="BTC",
            target_portion=0.2,
            total_balance=1000.0,
            executed="true",
            realized_pnl=pnl,
            signal_trigger_id=7,
            exchange="binance",
        )
    )
    db.commit()


class TestParseTriggerValue:
    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("DEPTH_RATIO buy-side imbalance triggered (7.76 vs threshold 7.315)", 7.76),
            ("DEPTH_RATIO triggered buy-side imbalance at 12.31 (threshold 7.3)", 12.31),
            ("Strong buy-side depth imbalance signal (DEPTH_RATIO=11.45 vs P90)", 11.45),
            ("DEPTH_RATIO surge above 30-day P90 threshold (current 31.2 vs 7.315)", 31.2),
            ("DEPTH_RATIO 买盘失衡 signal triggered with current value 7.996 (7.3)", 7.996),
        ],
    )
    def test_extracts_value_from_reason_variants(self, reason, expected):
        assert parse_trigger_value(reason, "DEPTH_RATIO") == pytest.approx(expected)

    def test_returns_none_when_factor_absent(self):
        assert parse_trigger_value("BTC dips below $63k amid ETF outflows", "DEPTH_RATIO") is None


class TestStratifiedReport:
    def test_insufficient_sample_gates_verdict(self, session):
        for i in range(5):
            _add(session, f"DEPTH_RATIO triggered at 8.{i} (threshold 7.3)", 10.0, minutes_ago=60 + i)

        report = signal_trigger_stratified_report(session, factor="DEPTH_RATIO", min_bucket_n=20)
        assert report["status"] == "insufficient_sample"
        assert all(b["status"] == "insufficient_sample" for b in report["buckets"] if b["n"])

    def test_buckets_by_extremity_and_reports_win_rates(self, session):
        # 25 normal-range wins, 25 extreme losses -> clean separation.
        for i in range(25):
            _add(session, "DEPTH_RATIO triggered at 8.5 (threshold 7.3)", 10.0, minutes_ago=100 + i)
        for i in range(25):
            _add(session, "DEPTH_RATIO surge (current 31.2 vs 7.315)", -10.0, minutes_ago=200 + i)

        report = signal_trigger_stratified_report(session, factor="DEPTH_RATIO", min_bucket_n=20)
        assert report["status"] == "ready"
        by_range = {b["range"]: b for b in report["buckets"]}
        assert by_range["<10"]["win_rate"] == pytest.approx(100.0)
        assert by_range["<10"]["status"] == "ok"
        assert by_range[">=20"]["win_rate"] == pytest.approx(0.0)
        assert by_range[">=20"]["status"] == "ok"

    def test_unparsed_reasons_counted_not_dropped_silently(self, session):
        _add(session, "DEPTH_RATIO triggered at 8.5", 10.0)
        _add(session, "signal fired, no value mentioned", -5.0, minutes_ago=90)

        report = signal_trigger_stratified_report(session, factor="DEPTH_RATIO", min_bucket_n=1)
        assert report["parsed"] == 1
        assert report["unparsed"] == 1

    def test_unsettled_decisions_excluded(self, session):
        _add(session, "DEPTH_RATIO triggered at 8.5", None)
        _add(session, "DEPTH_RATIO triggered at 8.6", 0, minutes_ago=90)

        report = signal_trigger_stratified_report(session, factor="DEPTH_RATIO", min_bucket_n=1)
        assert report["total_decisions"] == 0


class TestMainnetSignalGate:
    """问题.md §1: signals must be validated before driving real orders.
    Testnet IS the validation sandbox - it keeps trading to accumulate the
    record; mainnet execution requires that record to exist and be positive."""

    def _seed(self, session, n, pnl_each):
        for i in range(n):
            _add(session, f"DEPTH_RATIO triggered at 8.{i % 9} (threshold 7.3)",
                 pnl_each, minutes_ago=60 + i * 10)

    def _ctx(self):
        return {
            "trigger_type": "signal",
            "triggered_signals": [{"signal_name": "depth buy", "metric": "depth_ratio"}],
        }

    def test_blocks_when_sample_too_small(self, session):
        from services.signal_trigger_validation import signal_validation_gate

        self._seed(session, 6, 10.0)
        verdict = signal_validation_gate(session, self._ctx(), min_n=20)
        assert verdict["allowed"] is False
        assert "6" in verdict["reason"]

    def test_blocks_when_record_is_net_negative(self, session):
        from services.signal_trigger_validation import signal_validation_gate

        self._seed(session, 25, -5.0)
        verdict = signal_validation_gate(session, self._ctx(), min_n=20)
        assert verdict["allowed"] is False

    def test_allows_validated_profitable_signal(self, session):
        from services.signal_trigger_validation import signal_validation_gate

        self._seed(session, 25, 10.0)
        verdict = signal_validation_gate(session, self._ctx(), min_n=20)
        assert verdict["allowed"] is True

    def test_no_signal_context_passes_through(self, session):
        from services.signal_trigger_validation import signal_validation_gate

        assert signal_validation_gate(session, None)["allowed"] is True
        assert signal_validation_gate(session, {"trigger_type": "scheduled"})["allowed"] is True
