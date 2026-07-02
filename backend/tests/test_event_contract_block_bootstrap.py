"""Overlapping trades must use block bootstrap, not iid resampling."""
from services.event_contract.backtest_validation import _monte_carlo_report


def _trades(n=40):
    return [{"profit_loss": 80.0 if i % 3 else -100.0} for i in range(n)]


CFG_OVERLAP = {"non_overlapping_only": False, "expiry_minutes": 5, "period": "1m"}
CFG_CLEAN = {"non_overlapping_only": True, "expiry_minutes": 5, "period": "1m"}


def test_block_method_selected_for_overlapping():
    report = _monte_carlo_report(_trades(), CFG_OVERLAP)
    assert report["method"] == "block"
    assert report["block_length"] == 5


def test_iid_method_for_non_overlapping():
    report = _monte_carlo_report(_trades(), CFG_CLEAN)
    assert report["method"] == "iid"


def test_deterministic_with_seed():
    a = _monte_carlo_report(_trades(), CFG_OVERLAP)
    b = _monte_carlo_report(_trades(), CFG_OVERLAP)
    assert a == b
