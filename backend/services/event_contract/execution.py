"""Execution boundaries for event-contract Paper and Live modes.

This module is intentionally separate from the perpetual exchange clients.
Until a venue-specific event-contract adapter is registered, selecting Live
must stop before any order client can be reached.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol


class LiveEventContractAdapterUnavailable(RuntimeError):
    """Raised when Live was selected but no event-contract venue is available."""


class EventExecutionAdapter(Protocol):
    mode: str
    capabilities: Dict[str, bool]

    def open(self, **kwargs: Any) -> Dict[str, str]: ...

    def settle(self, **kwargs: Any) -> Dict[str, str]: ...

    def close(self, **kwargs: Any) -> Dict[str, str]: ...


class PaperEventExecutionAdapter:
    mode = "paper"
    capabilities = {"open": True, "settle": True, "close": False}

    def open(self, **_: Any) -> Dict[str, str]:
        return {"mode": "paper", "status": "simulated"}

    def settle(self, **_: Any) -> Dict[str, str]:
        return {"mode": "paper", "status": "settled_locally"}

    def close(self, **_: Any) -> Dict[str, str]:
        raise LiveEventContractAdapterUnavailable(
            "paper_event_contract_early_close_unavailable"
        )


class UnavailableLiveEventContractAdapter:
    mode = "live"
    capabilities = {"open": False, "settle": False, "close": False}

    def _unavailable(self) -> None:
        raise LiveEventContractAdapterUnavailable(
            "live_event_contract_adapter_unavailable"
        )

    def open(self, **_: Any) -> Dict[str, str]:
        self._unavailable()

    def settle(self, **_: Any) -> Dict[str, str]:
        self._unavailable()

    def close(self, **_: Any) -> Dict[str, str]:
        self._unavailable()


def resolve_event_execution_adapter(execution_mode: str) -> EventExecutionAdapter:
    """Resolve an event-contract adapter without falling back to perps."""
    mode = str(execution_mode or "paper").strip().lower()
    if mode == "paper":
        return PaperEventExecutionAdapter()
    if mode == "live":
        return UnavailableLiveEventContractAdapter()
    raise ValueError("Event-contract execution_mode must be paper or live")
