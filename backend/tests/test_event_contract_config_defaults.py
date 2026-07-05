"""Explicit zero economics must not be coerced back to defaults."""
from services.event_contract_service import event_contract_service


BASE = {
    "symbol": "BTC",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-01-02T00:00:00Z",
}


def _norm(extra):
    return event_contract_service._normalize_config({**BASE, **extra}, prediction=False)


def test_explicit_zero_payout_kept():
    assert _norm({"win_payout_ratio": 0})["win_payout_ratio"] == 0


def test_explicit_zero_delay_floored():
    # Execution-cost floors override explicit zero to enforce realistic assumptions.
    assert _norm({"delay_seconds": 0})["delay_seconds"] == 3


def test_delay_defaults_to_three_seconds():
    assert _norm({})["delay_seconds"] == 3


def test_payout_defaults_to_08():
    assert _norm({})["win_payout_ratio"] == 0.8
