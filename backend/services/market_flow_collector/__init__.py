"""
Market Flow Data Collector Service

Collects real-time market flow data from Hyperliquid using native SDK WebSocket:
- Trades (for CVD, Taker Volume)
- L2 Orderbook (for Depth Ratio, Liquidity)
- Asset Context (for OI, Funding Rate, Premium)

Data is aggregated in 15-second windows and persisted to database.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any
from collections import defaultdict

from hyperliquid.info import Info

from services.large_order_threshold_tracker import LargeOrderThresholdTracker

from services.market_flow_collector.constants import (
    AGGREGATION_WINDOW_SECONDS,
    HEALTH_CHECK_INTERVAL_SECONDS,
    DATA_STALE_THRESHOLD_SECONDS,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_BASE_DELAY_SECONDS,
    DEGRADED_MODE_RETRY_INTERVAL_SECONDS,
    DEGRADED_MODE_LOG_INTERVAL,
    TradeBuffer,
)
from services.market_flow_collector.ws_ingest import MarketFlowIngestMixin
from services.market_flow_collector.lifecycle import MarketFlowLifecycleMixin
from services.market_flow_collector.flush import MarketFlowFlushMixin
from services.market_flow_collector.maintenance import (
    DATA_RETENTION_DAYS,
    get_retention_days,
    cleanup_old_market_flow_data,
)

logger = logging.getLogger(__name__)


class MarketFlowCollector(
    MarketFlowIngestMixin,
    MarketFlowLifecycleMixin,
    MarketFlowFlushMixin,
):
    """
    Singleton service for collecting market flow data via WebSocket.
    Aggregates data in 15-second windows and persists to database.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.info: Optional[Info] = None
        self.running = False
        self.subscribed_symbols: List[str] = []
        self.subscription_ids: Dict[str, Dict[str, int]] = defaultdict(dict)

        # Data buffers
        self.trade_buffers: Dict[str, TradeBuffer] = {}
        self.latest_orderbook: Dict[str, Any] = {}
        self.latest_asset_ctx: Dict[str, Any] = {}

        # Data freshness tracking (timestamp of last update for each data source)
        self.last_update_time: Dict[str, float] = {
            "l2book": 0.0,
            "asset_ctx": 0.0,
            "trades": 0.0,
        }

        # Timing
        self.last_flush_time = time.time()
        self.flush_thread: Optional[threading.Thread] = None
        self.health_thread: Optional[threading.Thread] = None
        self.flush_wakeup = threading.Event()
        self.health_wakeup = threading.Event()
        self.flush_in_progress = threading.Lock()
        self.active_flush_started_at: Optional[float] = None

        # Reconnection state
        self.reconnect_attempts = 0
        self.is_reconnecting = False
        self.reconnect_lock = threading.Lock()

        # Degraded mode state (infinite retry when normal retries exhausted)
        self.degraded_mode = False
        self.degraded_retry_count = 0
        self.next_degraded_retry_at: Optional[float] = None

        # Thread safety
        self.buffer_lock = threading.Lock()
        self.large_order_tracker = LargeOrderThresholdTracker(exchange="hyperliquid")

        logger.info("MarketFlowCollector initialized")

    def _create_info_client(self, base_url: str) -> Info:
        """Create SDK Info, falling back to standard perps if HIP-3 metadata fails."""
        spot_meta = self._fetch_sanitized_spot_meta(base_url)
        try:
            return Info(base_url=base_url, skip_ws=False, spot_meta=spot_meta, perp_dexs=['', 'xyz'])
        except Exception as hip3_error:
            logger.warning(
                "Failed to load HIP-3 metadata for market flow collector; "
                "falling back to standard perps only: %s",
                hip3_error,
            )
            return Info(base_url=base_url, skip_ws=False, spot_meta=spot_meta, perp_dexs=[''])

    def _fetch_sanitized_spot_meta(self, base_url: str) -> Optional[Dict[str, Any]]:
        """Fetch spot metadata and remove malformed pairs before SDK initialization."""
        import requests

        try:
            resp = requests.post(f"{base_url.rstrip('/')}/info", json={"type": "spotMeta"}, timeout=10)
            resp.raise_for_status()
            spot_meta = resp.json()
        except Exception as err:
            logger.warning("Failed to fetch spot metadata for market flow collector: %s", err)
            return None

        if not isinstance(spot_meta, dict):
            return None

        tokens = spot_meta.get("tokens") or []
        valid_universe = []
        skipped = 0

        for spot_info in spot_meta.get("universe") or []:
            token_indexes = spot_info.get("tokens") if isinstance(spot_info, dict) else None
            if (
                isinstance(token_indexes, list)
                and all(isinstance(index, int) and 0 <= index < len(tokens) for index in token_indexes)
            ):
                valid_universe.append(spot_info)
            else:
                skipped += 1

        if skipped:
            logger.warning("Skipped %d malformed Hyperliquid spot metadata entries", skipped)

        sanitized = dict(spot_meta)
        sanitized["universe"] = valid_universe
        return sanitized


# Singleton instance
market_flow_collector = MarketFlowCollector()


__all__ = [
    "AGGREGATION_WINDOW_SECONDS",
    "HEALTH_CHECK_INTERVAL_SECONDS",
    "DATA_STALE_THRESHOLD_SECONDS",
    "MAX_RECONNECT_ATTEMPTS",
    "RECONNECT_BASE_DELAY_SECONDS",
    "DEGRADED_MODE_RETRY_INTERVAL_SECONDS",
    "DEGRADED_MODE_LOG_INTERVAL",
    "TradeBuffer",
    "MarketFlowCollector",
    "market_flow_collector",
    "DATA_RETENTION_DAYS",
    "get_retention_days",
    "cleanup_old_market_flow_data",
]
