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
