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


def test_coinglass_lag_floored_at_sampling_interval():
    # A lag tolerance below the CG sampling interval makes the features dead
    # ~93% of the time (trader #2 ran 120s tolerance against 30m data and every
    # live bet had reversal_evidence_score=0). Floor at one full interval.
    cfg = _norm({
        "enable_coinglass_features": True,
        "coinglass_interval": "30m",
        "max_coinglass_lag_seconds": 120,
    })
    assert cfg["max_coinglass_lag_seconds"] == 1800


def test_coinglass_lag_above_interval_kept():
    cfg = _norm({
        "enable_coinglass_features": True,
        "coinglass_interval": "30m",
        "max_coinglass_lag_seconds": 3600,
    })
    assert cfg["max_coinglass_lag_seconds"] == 3600
