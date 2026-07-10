"""Paper/Live execution boundaries for event-contract production traders."""

from __future__ import annotations

import pytest

from services.event_contract.execution import (
    LiveEventContractAdapterUnavailable,
    PaperEventExecutionAdapter,
    resolve_event_execution_adapter,
)


def test_paper_adapter_is_simulation_only():
    adapter = resolve_event_execution_adapter("paper")

    assert isinstance(adapter, PaperEventExecutionAdapter)
    assert adapter.mode == "paper"
    assert adapter.capabilities == {"open": True, "settle": True, "close": False}
    assert adapter.open(symbol="BTC", direction="long", stake=100) == {
        "mode": "paper",
        "status": "simulated",
    }


def test_live_mode_fails_closed_without_event_contract_capability():
    adapter = resolve_event_execution_adapter("live")

    assert adapter.mode == "live"
    assert adapter.capabilities == {"open": False, "settle": False, "close": False}
    with pytest.raises(LiveEventContractAdapterUnavailable, match="live_event_contract_adapter_unavailable"):
        adapter.open(symbol="BTC", direction="long", stake=100)


def test_execution_mode_is_not_perpetual_order_routing():
    with pytest.raises(ValueError, match="paper or live"):
        resolve_event_execution_adapter("binance_perpetual")
