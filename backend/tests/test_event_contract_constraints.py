"""Non-overlap, spacing and daily-loss-cap constraints."""
from services.event_contract.backtest_constraints import TradeConstraintTracker

DAY = 86400


def _tracker(**kw):
    defaults = {"non_overlapping": True, "min_seconds_between_trades": 0, "daily_loss_cap": None}
    return TradeConstraintTracker(**{**defaults, **kw})


def test_overlap_blocked_until_settlement():
    t = _tracker()
    assert t.allow(1000) is None
    t.record(entry_ts=1000, settlement_ts=1300, pnl=0.0)
    assert t.allow(1200) == "overlap_skipped_count"
    assert t.allow(1300) is None


def test_min_spacing():
    t = _tracker(non_overlapping=False, min_seconds_between_trades=60)
    t.record(entry_ts=1000, settlement_ts=1300, pnl=0.0)
    assert t.allow(1030) == "frequency_skipped_count"
    assert t.allow(1060) is None


def test_daily_loss_cap_blocks_same_utc_day_only():
    t = _tracker(daily_loss_cap=100.0)
    t.record(entry_ts=1000, settlement_ts=1300, pnl=-100.0)
    assert t.allow(2000) == "daily_cap_skipped_count"
    assert t.allow(1000 + DAY) is None
