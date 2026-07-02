"""Strategy fingerprint must ignore the time window, nothing else."""
from services.event_contract_service import event_contract_service

BASE = {
    "symbol": "BTC",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-01-02T00:00:00Z",
}


def _fp(extra):
    cfg = event_contract_service._normalize_config({**BASE, **extra}, prediction=False)
    return event_contract_service._strategy_fingerprint(cfg)


def test_window_change_keeps_fingerprint():
    assert _fp({}) == _fp({"start_time": "2026-03-01T00:00:00Z", "end_time": "2026-03-02T00:00:00Z"})


def test_parameter_change_changes_fingerprint():
    assert _fp({}) != _fp({"enable_trap_filter": False})


def test_reviewer_weights_ignored_in_fingerprint():
    """Regression: reviewer_weights is injected at runtime based on window start,
    so it must be excluded from fingerprint. Two identical strategies on different
    windows should have the same fingerprint even with different weights."""
    cfg1 = event_contract_service._normalize_config({**BASE}, prediction=False)
    cfg1_with_weights = {**cfg1, "reviewer_weights": {"alice": 1.2, "bob": 0.8}}

    cfg2 = event_contract_service._normalize_config(
        {**BASE, "start_time": "2026-03-01T00:00:00Z", "end_time": "2026-03-02T00:00:00Z"},
        prediction=False,
    )
    cfg2_with_weights = {**cfg2, "reviewer_weights": {"alice": 0.7, "bob": 1.5}}

    # Same strategy on different windows with different weights should have same fingerprint
    fp1 = event_contract_service._strategy_fingerprint(cfg1_with_weights)
    fp2 = event_contract_service._strategy_fingerprint(cfg2_with_weights)
    assert fp1 == fp2, "Fingerprints should match when only window and weights differ"

    # But a real parameter change should still produce different fingerprints
    cfg3 = event_contract_service._normalize_config(
        {**BASE, "enable_trap_filter": False}, prediction=False
    )
    cfg3_with_weights = {**cfg3, "reviewer_weights": {"alice": 1.2, "bob": 0.8}}
    fp3 = event_contract_service._strategy_fingerprint(cfg3_with_weights)
    assert fp1 != fp3, "Fingerprints should differ when strategy parameters differ"
