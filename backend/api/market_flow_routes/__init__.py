"""
Market Flow Indicators API Routes

Provides aggregated market flow indicators:
- CVD (Cumulative Volume Delta)
- Taker Buy/Sell Volume
- OI (Open Interest) - absolute and delta
- Funding Rate
- Depth Ratio
- Order Imbalance

This package was split from a single module. The public contract
(`router`, `decimal_to_float`, `TIMEFRAME_MS`, `_build_market_flow_summary_item`)
remains importable from `api.market_flow_routes`.
"""

from ._base import (
    router,
    get_db,
    logger,
    TIMEFRAME_MS,
    decimal_to_float,
    floor_timestamp,
    IndicatorDataPoint,
    TakerVolumeDataPoint,
    MarketFlowResponse,
    MarketFlowSummaryItem,
    MarketFlowSummaryResponse,
    LargeOrderZoneItem,
    LargeOrderZoneResponse,
)

# Import endpoint modules to register their routes on the shared router.
from . import summary as _summary  # noqa: E402,F401
from . import indicators as _indicators  # noqa: E402,F401

from .summary import (
    get_market_flow_summary,
    get_large_order_zones,
    _build_market_flow_summary_item,
)
from .indicators import get_market_flow_indicators

__all__ = [
    "router",
    "get_db",
    "logger",
    "TIMEFRAME_MS",
    "decimal_to_float",
    "floor_timestamp",
    "IndicatorDataPoint",
    "TakerVolumeDataPoint",
    "MarketFlowResponse",
    "MarketFlowSummaryItem",
    "MarketFlowSummaryResponse",
    "LargeOrderZoneItem",
    "LargeOrderZoneResponse",
    "get_market_flow_summary",
    "get_large_order_zones",
    "_build_market_flow_summary_item",
    "get_market_flow_indicators",
]
