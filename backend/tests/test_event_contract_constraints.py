"""Non-overlap, spacing and daily-loss-cap constraints."""
from services.event_contract.backtest_constraints import TradeConstraintTracker

DAY = 86400


def _tracker(**kw):
    defaults = {"non_overlapping": True, "min_seconds_between_trades": 0, "daily_loss_cap": None}
    return TradeConstraintTracker(**{**defaults, **kw})


def test_overlap_blocked_until_settlement():
    t = _tracker()
    assert t.allow(1000, 1000) is None
    t.record(entry_ts=1000, settlement_ts=1300, pnl=0.0)
    assert t.allow(1200, 1200) == "overlap_skipped_count"
    assert t.allow(1300, 1300) is None


def test_min_spacing():
    t = _tracker(non_overlapping=False, min_seconds_between_trades=60)
    t.record(entry_ts=1000, settlement_ts=1300, pnl=0.0)
    assert t.allow(1030, 1030) == "frequency_skipped_count"
    assert t.allow(1060, 1060) is None


def test_daily_loss_cap_blocks_same_utc_day_only():
    t = _tracker(daily_loss_cap=100.0)
    t.record(entry_ts=1000, settlement_ts=1300, pnl=-100.0)
    assert t.allow(2000, 2000) == "daily_cap_skipped_count"
    assert t.allow(1000 + DAY, 1000 + DAY) is None


def test_daily_loss_cap_keyed_by_entry_day_not_decision_day():
    """Regression: a decision made late on day 0 whose entry resolves into day 1
    must be checked against day 1's accumulated loss (the same bucket record()
    uses), not day 0's. Likewise, a decision that resolves into day 2 must not
    be blocked by day 1's breach - the cap resets per entry day."""
    t = _tracker(non_overlapping=False, daily_loss_cap=100.0)
    # Loss recorded against day 1 (entry_ts on day 1), breaching the cap.
    t.record(entry_ts=DAY, settlement_ts=DAY + 300, pnl=-150.0)
    # Decision made late on day 0, but its entry resolves into day 1 -> must be
    # blocked because day 1's cap is already breached.
    assert t.allow(DAY - 10, DAY) == "daily_cap_skipped_count"
    # Decision/entry both on day 2 -> new day, cap resets.
    assert t.allow(2 * DAY, 2 * DAY) is None
