"""Platform presets must inject each venue's real rules."""
import pytest

from services.event_contract_service import event_contract_service

BASE = {
    "symbol": "BTC",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-01-02T00:00:00Z",
}


def _norm(extra):
    return event_contract_service._normalize_config({**BASE, **extra}, prediction=False)


def test_binance_event_preset():
    cfg = _norm({"platform": "binance_event"})
    assert cfg["draw_result"] == "refund"
    assert cfg["win_payout_ratio"] == 0.8
    assert cfg["daily_loss_cap"] == 10000
    assert cfg["min_stake"] == 5


def test_hibt_preset_sets_trade_spacing():
    cfg = _norm({"platform": "hibt"})
    assert cfg["min_seconds_between_trades"] == 60
    assert cfg["min_stake"] == 3


def test_stake_below_platform_minimum_rejected():
    with pytest.raises(ValueError):
        _norm({"platform": "binance_event", "stake_amount": 4})


def test_user_override_survives_preset():
    cfg = _norm({"platform": "hibt", "win_payout_ratio": 0.85})
    assert cfg["win_payout_ratio"] == 0.85


def test_refund_draw_settles_as_draw():
    result = event_contract_service._settle_event_contract("long", 100.0, 100.0, "refund")
    assert result == "draw"
