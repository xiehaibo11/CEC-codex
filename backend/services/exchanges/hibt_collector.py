"""HiBT REST market-flow collector.

HiBT currently exposes recent public trades through ``/v2/market/deals``. The
endpoint is not a deep historical feed, so this collector polls the latest
window and stores taker buy/sell buckets into ``market_trades_aggregated`` for
the same coverage heatmap and signal paths used by Binance/Hyperliquid.
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database.connection import SessionLocal
from services.exchanges.data_persistence import ExchangeDataPersistence
from services.hibt_market_data import fetch_hibt_deals

logger = logging.getLogger(__name__)

DEALS_INTERVAL_SECONDS = 15


class HibtCollector:
    """Poll HiBT public deals and persist taker-flow buckets."""

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
        self.scheduler: Optional[BackgroundScheduler] = None
        self.running = False
        self.symbols: List[str] = []
        logger.info("HibtCollector initialized")

    def start(self, symbols: Optional[List[str]] = None):
        """Start polling HiBT deals for the configured watchlist."""
        if self.running:
            logger.warning("HibtCollector already running")
            return

        if symbols is None:
            from services.hibt_symbol_service import get_selected_symbols

            symbols = get_selected_symbols() or ["BTC"]
            logger.info("[HiBT] Using HiBT watchlist symbols: %s", symbols)

        self.symbols = symbols or ["BTC"]
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            func=self._collect_deals,
            trigger=IntervalTrigger(seconds=DEALS_INTERVAL_SECONDS),
            id="hibt_deals",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        self.running = True
        logger.info("[HiBT] Collector started with symbols: %s", self.symbols)

        # Prime coverage immediately after startup instead of waiting one
        # interval for the data-collection page to show a symbol.
        self._collect_deals()

    def stop(self):
        """Stop polling HiBT deals."""
        if not self.running:
            return

        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
        self.running = False
        logger.info("[HiBT] Collector stopped")

    def refresh_symbols(self, new_symbols: List[str]):
        """Update symbols used by the next polling run."""
        self.symbols = new_symbols or ["BTC"]
        logger.info("[HiBT] Collector symbols updated: %s", self.symbols)

    def _collect_deals(self):
        """Collect recent public trades for all symbols."""
        if not self.symbols:
            return

        db = SessionLocal()
        try:
            persistence = ExchangeDataPersistence(db)
            for symbol in self.symbols:
                try:
                    trades = fetch_hibt_deals(symbol)
                    if not trades:
                        logger.debug("[HiBT] No deals returned for %s", symbol)
                        continue
                    result = persistence.upsert_taker_trades_bulk(trades, bucket_seconds=DEALS_INTERVAL_SECONDS)
                    logger.debug(
                        "[HiBT] Deals %s: upserted %s buckets from %s trades",
                        symbol,
                        result.get("upserted", 0),
                        len(trades),
                    )
                except Exception as err:  # noqa: BLE001 - keep other symbols collecting
                    logger.error("[HiBT] Failed to collect deals for %s: %s", symbol, err)
        finally:
            db.close()


hibt_collector = HibtCollector()

