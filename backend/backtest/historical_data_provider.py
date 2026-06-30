"""
Historical Data Provider for Backtest

Provides historical market data for backtesting.
Interface compatible with DataProvider for strategy code reuse.

The implementation is split by responsibility:
- KlineLoaderMixin (historical_kline_loader.py): kline DB/API loading + caching.
- MarketQueryMixin (historical_market_queries.py): price/indicator/flow/regime/
  factor read API constrained to current_time_ms.
This module owns construction, simulation-time control, and query logging.
"""

import logging
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from .historical_kline_loader import KlineLoaderMixin
from .historical_market_queries import MarketQueryMixin

logger = logging.getLogger(__name__)


class HistoricalDataProvider(KlineLoaderMixin, MarketQueryMixin):
    """
    Provides historical data for backtesting.

    Key differences from DataProvider:
    - Reads from database instead of real-time API
    - Filters data by current_time_ms (only data before this time)
    - Used by backtest engine to simulate historical market state
    - Tracks data queries for logging
    """

    def __init__(
        self,
        db: Session,
        symbols: List[str],
        start_time_ms: int,
        end_time_ms: int,
        exchange: str = "hyperliquid",
    ):
        """
        Initialize historical data provider.

        Args:
            db: Database session
            symbols: List of symbols to load data for
            start_time_ms: Backtest start time (milliseconds)
            end_time_ms: Backtest end time (milliseconds)
            exchange: Exchange to use for data (default: hyperliquid)
        """
        self.db = db
        self.symbols = symbols
        self.start_time_ms = start_time_ms
        self.end_time_ms = end_time_ms
        self.current_time_ms = start_time_ms
        self.exchange = exchange

        # Caches
        self._kline_cache: Dict[str, List[Dict]] = {}
        self._flow_cache: Dict[str, Dict] = {}
        self._price_cache: Dict[str, float] = {}

        # Query tracking for logging
        self._query_log: List[Dict[str, Any]] = []

        # Preload data for better performance
        self._preload_data()

    def set_current_time(self, timestamp_ms: int):
        """Set current simulation time."""
        self.current_time_ms = timestamp_ms
        # Clear price cache when time changes
        self._price_cache = {}

    def clear_query_log(self):
        """Clear query log for new trigger."""
        self._query_log = []

    def get_query_log(self) -> List[Dict[str, Any]]:
        """Get list of data queries made since last clear."""
        return self._query_log.copy()

    def _log_query(self, method: str, args: Dict[str, Any], result: Any):
        """Log a data query with full result for debugging.

        Args:
            method: Query method name (e.g., 'get_klines', 'get_indicator')
            args: Query arguments dict
            result: Query result (will be serialized)
        """
        self._query_log.append({
            "method": method,
            "args": args,
            "result": result
        })
