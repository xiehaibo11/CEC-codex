"""
Signal Detection Service

Detects signal triggers based on market flow data.
Uses edge-triggered logic: only triggers when condition changes from False to True.
"""

from services.signal_detection_service.states import (
    SignalState,
    PoolState,
    _get_market_regime_for_trigger,
)
from services.signal_detection_service.service import (
    SignalDetectionService,
    signal_detection_service,
)

__all__ = [
    "SignalState",
    "PoolState",
    "SignalDetectionService",
    "signal_detection_service",
    "_get_market_regime_for_trigger",
]
