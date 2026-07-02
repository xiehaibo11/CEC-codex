"""Trading-session (UTC hours) filter for the event-contract backtest."""
import pytest

from services.event_contract_service import event_contract_service

BASE = {
    "symbol": "BTC",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-01-02T00:00:00Z",
}


def _norm(extra):
    return event_contract_service._normalize_config({**BASE, **extra}, prediction=False)


def test_default_allows_all_hours():
    assert _norm({})["allowed_utc_hours"] is None


def test_hours_normalized_sorted_deduped():
    cfg = _norm({"allowed_utc_hours": [23, 8, 8, 9]})
    assert cfg["allowed_utc_hours"] == [8, 9, 23]


def test_invalid_hour_rejected():
    with pytest.raises(ValueError):
        _norm({"allowed_utc_hours": [8, 24]})


def test_empty_list_means_all_hours():
    assert _norm({"allowed_utc_hours": []})["allowed_utc_hours"] is None


def test_decision_hour_allowed_helper():
    allowed = [8, 9, 10]
    # 2026-01-01T09:30:00Z -> hour 9 allowed; 03:30 -> blocked
    ts_ok = 1767259800   # 2026-01-01 09:30:00 UTC
    ts_no = 1767238200   # 2026-01-01 03:30:00 UTC
    assert event_contract_service._session_allows(ts_ok, allowed) is True
    assert event_contract_service._session_allows(ts_no, allowed) is False
    assert event_contract_service._session_allows(ts_no, None) is True
