"""Platform-aware execution-cost model.

Event-contract venues (hibt, binance_event) have NO separate trading fee —
the house edge lives in the 0.8 payout — and the strike is set at the venue
index/mark price at confirmation, so order-book slippage/impact do not apply
(sources documented in services/event_contract/platforms.py). Perp-style
floors stay enforced for custom/unknown venues.
"""
import pytest

from services.event_contract_service import EventContractService


@pytest.fixture()
def svc():
    return EventContractService()


def _normalize(svc, **overrides):
    raw = {"symbol": "BTC", "exchange": "binance", "period": "1m", **overrides}
    return svc._normalize_config(raw, prediction=True)


def test_hibt_uses_documented_real_costs(svc):
    cfg = _normalize(svc, platform="hibt")
    assert cfg["fee_rate"] == 0.0          # documented: no separate fee
    assert cfg["slippage_bps"] == 0.0      # strike at venue mark price, no book crossing
    assert cfg["impact_cost_bps"] == 0.0
    assert cfg["delay_seconds"] >= 3       # confirmation delay stays floored
    assert cfg["win_payout_ratio"] == 0.8  # house edge lives here
    assert cfg["_platform_cost_model"] == "event_contract_documented"
    floor_params = {f["param"] for f in cfg["_enforced_cost_floors"]}
    assert "fee_rate" not in floor_params
    assert "slippage_bps" not in floor_params


def test_binance_event_uses_documented_real_costs(svc):
    cfg = _normalize(svc, platform="binance_event")
    assert cfg["fee_rate"] == 0.0
    assert cfg["slippage_bps"] == 0.0
    assert cfg["draw_result"] == "refund"  # documented: draw refunds premium
    assert cfg["_platform_cost_model"] == "event_contract_documented"


def test_custom_platform_keeps_conservative_floors(svc):
    cfg = _normalize(svc, platform="custom", fee_rate=0, slippage_bps=0)
    assert cfg["fee_rate"] == 0.001
    assert cfg["slippage_bps"] == 2.0
    assert cfg["impact_cost_bps"] >= 0.5  # default 1.0 already above the floor
    assert cfg["_platform_cost_model"] == "custom_floored"
    floor_params = {f["param"] for f in cfg["_enforced_cost_floors"]}
    assert {"fee_rate", "slippage_bps"} <= floor_params


def test_explicit_fee_on_event_platform_is_respected(svc):
    """A user-supplied fee (e.g. a venue running a promo fee) must not be
    silently zeroed — presets only fill fields the user left unset."""
    cfg = _normalize(svc, platform="hibt", fee_rate=0.0005)
    assert cfg["fee_rate"] == 0.0005
