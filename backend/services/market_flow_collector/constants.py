"""Shared constants and buffer dataclass for the market flow collector."""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field

# Aggregation window in seconds
AGGREGATION_WINDOW_SECONDS = 15

# Connection health check settings
HEALTH_CHECK_INTERVAL_SECONDS = 30
DATA_STALE_THRESHOLD_SECONDS = 30  # Consider data stale if no update for 30s
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_BASE_DELAY_SECONDS = 5

# Degraded mode settings (infinite retry with longer intervals)
DEGRADED_MODE_RETRY_INTERVAL_SECONDS = 120  # 2 minutes between retries
DEGRADED_MODE_LOG_INTERVAL = 5  # Log warning every 5 failed attempts


@dataclass
class TradeBuffer:
    """Buffer for aggregating trades within a time window"""
    taker_buy_volume: Decimal = Decimal("0")
    taker_sell_volume: Decimal = Decimal("0")
    taker_buy_count: int = 0
    taker_sell_count: int = 0
    taker_buy_notional: Decimal = Decimal("0")
    taker_sell_notional: Decimal = Decimal("0")
    large_buy_notional: Decimal = Decimal("0")
    large_sell_notional: Decimal = Decimal("0")
    large_buy_count: int = 0
    large_sell_count: int = 0
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    total_volume: Decimal = Decimal("0")
    total_notional: Decimal = Decimal("0")

    def reset(self):
        """Reset buffer for next window"""
        self.taker_buy_volume = Decimal("0")
        self.taker_sell_volume = Decimal("0")
        self.taker_buy_count = 0
        self.taker_sell_count = 0
        self.taker_buy_notional = Decimal("0")
        self.taker_sell_notional = Decimal("0")
        self.large_buy_notional = Decimal("0")
        self.large_sell_notional = Decimal("0")
        self.large_buy_count = 0
        self.large_sell_count = 0
        self.high_price = None
        self.low_price = None
        self.total_volume = Decimal("0")
        self.total_notional = Decimal("0")
