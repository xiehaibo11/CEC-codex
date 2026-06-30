"""
Market Flow Indicators API - shared base.

Defines the shared APIRouter, DB session dependency, timeframe constants,
Pydantic response models, and small conversion helpers used by all
market-flow endpoint modules.
"""

import logging
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

from database.connection import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market-flow", tags=["market-flow"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Timeframe to milliseconds mapping
TIMEFRAME_MS = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "8h": 8 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


class IndicatorDataPoint(BaseModel):
    time: int  # Unix timestamp in seconds (for chart compatibility)
    value: Optional[float] = None


class TakerVolumeDataPoint(BaseModel):
    time: int
    buy: float
    sell: float


class MarketFlowResponse(BaseModel):
    symbol: str
    timeframe: str
    data_available_from: Optional[int] = None
    indicators: Dict[str, List[Any]]


class MarketFlowSummaryItem(BaseModel):
    symbol: str
    exchange: str
    window: str
    start_time: int
    end_time: int
    latest_trade_timestamp: Optional[int] = None
    total_buy_notional: float = 0
    total_sell_notional: float = 0
    net_inflow: float = 0
    buy_ratio: float = 0
    total_large_buy_notional: float = 0
    total_large_sell_notional: float = 0
    large_order_net: float = 0
    retail_net: float = 0
    large_buy_count: int = 0
    large_sell_count: int = 0
    open_interest_change_pct: Optional[float] = None
    funding_rate_pct: Optional[float] = None


class MarketFlowSummaryResponse(BaseModel):
    exchange: str
    window: str
    items: List[MarketFlowSummaryItem]


class LargeOrderZoneItem(BaseModel):
    time: int
    large_buy_notional: float = 0
    large_sell_notional: float = 0
    large_order_net: float = 0
    large_buy_count: int = 0
    large_sell_count: int = 0


class LargeOrderZoneResponse(BaseModel):
    symbol: str
    exchange: str
    timeframe: str
    items: List[LargeOrderZoneItem]


def decimal_to_float(val) -> Optional[float]:
    """Convert Decimal to float, handling None"""
    if val is None:
        return None
    return float(val)


def floor_timestamp(ts_ms: int, interval_ms: int) -> int:
    """Floor timestamp to interval boundary"""
    return (ts_ms // interval_ms) * interval_ms
