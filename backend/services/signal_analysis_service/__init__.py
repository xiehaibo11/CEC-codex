"""
Signal Analysis Service

Provides statistical analysis of market flow indicators to help users
set appropriate signal thresholds.
"""

from services.signal_analysis_service.core import (
    LIMITED_DATA_THRESHOLD,
    MIN_SAMPLES,
    SignalAnalysisService,
    signal_analysis_service,
)
from services.signal_analysis_service.history import MetricHistoryMixin

__all__ = [
    "LIMITED_DATA_THRESHOLD",
    "MIN_SAMPLES",
    "MetricHistoryMixin",
    "SignalAnalysisService",
    "signal_analysis_service",
]
