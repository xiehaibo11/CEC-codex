"""Production event-contract policy: trend-follow only, fixed expiries and guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.event_contract_routes import BacktestRequest, PredictRequest
from services.event_contract.production_policy import (
    DEFAULT_PRODUCTION_CONFIG,
    normalize_production_config,
)


def test_production_policy_accepts_only_five_or_ten_minute_expiry():
    for expiry_minutes in (5, 10):
        config = normalize_production_config({"expiry_minutes": expiry_minutes})
        assert config["expiry_minutes"] == expiry_minutes

    for expiry_minutes in (1, 3, 15, 30, 60):
        with pytest.raises(ValueError, match="5 or 10"):
            normalize_production_config({"expiry_minutes": expiry_minutes})


def test_production_policy_defaults_to_trend_follow_and_paper():
    config = normalize_production_config({})

    assert config["expiry_minutes"] == 5
    assert config["signal_mode"] == "trend_follow"
    assert config["execution_mode"] == "paper"
    assert config["leverage"] == 10
    assert config["trade_margin"] == 100
    assert config["max_daily_trades"] == 10
    assert config["profit_target_multiplier"] == 2
    assert config["non_overlapping_only"] is True
    assert config["period"] == "1m"
    assert config["professional_ai_enabled"] is True
    assert config["professional_ai_min_confidence"] == 75

    assert DEFAULT_PRODUCTION_CONFIG["signal_mode"] == "trend_follow"


@pytest.mark.parametrize("signal_mode", ["range_boundary", "exhaustion_fade"])
def test_production_policy_rejects_countertrend_modes(signal_mode: str):
    with pytest.raises(ValueError, match="trend_follow"):
        normalize_production_config({"signal_mode": signal_mode})


def test_production_policy_rejects_ai_overrides_to_hard_risk_fields():
    config = normalize_production_config(
        {
            "non_overlapping_only": False,
            "leverage": 25,
            "max_daily_trades": 100,
            "profit_target_multiplier": 1.5,
        }
    )

    assert config["non_overlapping_only"] is True
    assert config["leverage"] == 10
    assert config["max_daily_trades"] == 10
    assert config["profit_target_multiplier"] == 2


def test_live_mode_is_explicit_but_requires_a_registered_adapter():
    config = normalize_production_config({"execution_mode": "live"})
    assert config["execution_mode"] == "live"

    with pytest.raises(ValueError, match="Live event-contract adapter"):
        normalize_production_config({"execution_mode": "unsupported"})


def test_api_schema_defaults_to_production_expiry_and_trend_follow():
    payload = PredictRequest()

    assert payload.expiry_minutes == 5
    assert payload.signal_mode == "trend_follow"

    with pytest.raises(ValidationError):
        PredictRequest(expiry_minutes=15)


def test_backtest_api_schema_rejects_non_production_expiry():
    with pytest.raises(ValidationError):
        BacktestRequest(
            start_time="2026-07-01T00:00:00Z",
            end_time="2026-07-02T00:00:00Z",
            expiry_minutes=3,
        )


def test_production_policy_rejects_non_one_minute_base_feed():
    with pytest.raises(ValueError, match="1m base"):
        normalize_production_config({"period": "5m"})
