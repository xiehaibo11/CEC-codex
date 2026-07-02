"""Strike must come from the first observable bar OPEN at/after the decision."""
from services.event_contract_service import event_contract_service


def _klines(start=1000, interval=60, count=10, open_base=100.0):
    return [
        {"timestamp": start + i * interval, "open": open_base + i, "high": 0, "low": 0,
         "close": open_base + i + 0.5, "volume": 1.0}
        for i in range(count)
    ]


def test_entry_bar_is_bar_opening_at_decision_ts():
    klines = _klines()
    # decision at close of bar 0 => decision_ts = 1060 = open ts of bar 1
    idx, lag = event_contract_service._resolve_entry_bar(klines, 1060, 3, 60, 60)
    assert idx == 1
    assert lag == 0
    assert klines[idx]["open"] == 101.0


def test_delay_longer_than_bar_advances_entry():
    klines = _klines()
    # delay 61s pushes target into bar 2 [1120, 1180)
    idx, _ = event_contract_service._resolve_entry_bar(klines, 1060, 61, 60, 120)
    assert idx == 2


def test_gap_exceeding_lag_tolerance_returns_none():
    klines = _klines()[:2] + _klines(start=1600, count=3)  # gap after bar 1
    idx, lag = event_contract_service._resolve_entry_bar(klines, 1120, 3, 60, 60)
    assert idx is None
    assert lag > 60
