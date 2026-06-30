#!/usr/bin/env python3
"""
Market Flow Indicators Service for AI Prompt Variables

Provides aggregated market flow data formatted for AI prompt injection.
Unlike the chart API which returns time series, this returns:
- Current value
- Last N period values
- Relevant context (e.g., averages for comparison)

Supported variables:
- {SYMBOL}_CVD_{PERIOD} - Cumulative Volume Delta
- {SYMBOL}_TAKER_{PERIOD} - Taker Buy/Sell Volume and Ratio
- {SYMBOL}_OI_{PERIOD} - Open Interest
- {SYMBOL}_FUNDING_{PERIOD} - Funding Rate
- {SYMBOL}_DEPTH_{PERIOD} - Order Book Depth Ratio

This package preserves the original ``services.market_flow_indicators`` module
import surface: every public name is re-exported here.
"""

from services.market_flow_indicators.common import (
    INSUFFICIENT_DATA_WARNING_COOLDOWN_SECONDS,
    _insufficient_data_lock,
    _insufficient_data_warning_at,
    _log_insufficient_data_once,
    TIMEFRAME_MS,
    floor_timestamp,
    decimal_to_float,
    format_volume,
)
from services.market_flow_indicators.trade_indicators import (
    _get_cvd_data,
    _get_taker_data,
    _get_price_change_data,
    _get_volatility_data,
)
from services.market_flow_indicators.metric_indicators import (
    _get_oi_data,
    _get_oi_delta_data,
    _get_funding_data,
)
from services.market_flow_indicators.orderbook_indicators import (
    _get_depth_data,
    _get_imbalance_data,
)
from services.market_flow_indicators.aggregation import (
    get_indicator_value,
    get_flow_indicators_for_prompt,
)

__all__ = [
    "INSUFFICIENT_DATA_WARNING_COOLDOWN_SECONDS",
    "_insufficient_data_lock",
    "_insufficient_data_warning_at",
    "_log_insufficient_data_once",
    "TIMEFRAME_MS",
    "floor_timestamp",
    "decimal_to_float",
    "format_volume",
    "get_indicator_value",
    "get_flow_indicators_for_prompt",
    "_get_cvd_data",
    "_get_taker_data",
    "_get_oi_data",
    "_get_oi_delta_data",
    "_get_funding_data",
    "_get_depth_data",
    "_get_imbalance_data",
    "_get_price_change_data",
    "_get_volatility_data",
]
