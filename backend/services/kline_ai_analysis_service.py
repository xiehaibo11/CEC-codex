"""
K-line AI Analysis Service - Handles AI-powered chart analysis

This module was split by responsibility into the ``kline_ai_analysis_service``
package. It remains importable at its original path and re-exports every public
name:
- ``formatting``: summary formatters (SafeDict, _format_* helpers).
- ``analysis``: analyze_kline_chart, get_analysis_history.
"""
import logging
import os

__path__ = [os.path.join(os.path.dirname(__file__), "kline_ai_analysis_service")]

from services.kline_ai_analysis_service.formatting import (  # noqa: E402
    SafeDict,
    _format_klines_summary,
    _format_positions_summary,
    _format_indicators_summary,
    _format_flow_indicators_summary,
    _format_volume,
)
from services.kline_ai_analysis_service.analysis import (  # noqa: E402
    analyze_kline_chart,
    get_analysis_history,
)

logger = logging.getLogger(__name__)

__all__ = [
    "SafeDict",
    "_format_klines_summary",
    "_format_positions_summary",
    "_format_indicators_summary",
    "_format_flow_indicators_summary",
    "_format_volume",
    "analyze_kline_chart",
    "get_analysis_history",
]
