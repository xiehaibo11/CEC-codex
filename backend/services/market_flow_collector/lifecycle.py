"""Collector lifecycle: start/stop, worker threads, health monitoring, reconnect."""

import time
import logging
import threading
from typing import List, Optional

from services.market_flow_collector.constants import (
    AGGREGATION_WINDOW_SECONDS,
    HEALTH_CHECK_INTERVAL_SECONDS,
    DATA_STALE_THRESHOLD_SECONDS,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_BASE_DELAY_SECONDS,
    DEGRADED_MODE_RETRY_INTERVAL_SECONDS,
    DEGRADED_MODE_LOG_INTERVAL,
)

logger = logging.getLogger(__name__)


class MarketFlowLifecycleMixin:
    """Start/stop, worker thread management, health checks and reconnection."""

    def start(self, symbols: Optional[List[str]] = None):
        """Start the collector with given symbols or from watchlist"""
        if self.running:
            logger.warning("MarketFlowCollector already running")
            return

        # Get symbols from watchlist if not provided
        if symbols is None:
            from services.hyperliquid_symbol_service import get_selected_symbols
            symbols = get_selected_symbols()

        if not symbols:
            logger.warning("No symbols to monitor, collector not started")
            return

        # Store symbols for retry
        self._pending_symbols = symbols
        self.reconnect_attempts = 0
        self.large_order_tracker.initialize_from_history(symbols)

        # Try to start with retry logic
        self._start_with_retry()

    def _start_with_retry(self):
        """Internal method to start collector with retry on failure"""
        symbols = getattr(self, '_pending_symbols', None)
        if not symbols:
            logger.warning("No pending symbols for retry")
            return

        try:
            base_url = "https://api.hyperliquid.xyz"
            logger.info(f"[Start] Connecting to Hyperliquid API: {base_url}")
            self.info = self._create_info_client(base_url)

            self.running = True
            self.subscribed_symbols = []
            self.reconnect_attempts = 0

            for symbol in symbols:
                self._subscribe_symbol(symbol)

            self._ensure_worker_threads()

            logger.info(f"MarketFlowCollector started with symbols: {symbols}")

        except Exception as e:
            logger.error(f"Failed to start MarketFlowCollector: {e}", exc_info=True)
            self.running = False

            self.reconnect_attempts += 1
            if self.reconnect_attempts <= MAX_RECONNECT_ATTEMPTS:
                delay = RECONNECT_BASE_DELAY_SECONDS * (2 ** (self.reconnect_attempts - 1))
                logger.warning(
                    f"[Start] Will retry in {delay}s "
                    f"(attempt {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})"
                )
                retry_timer = threading.Timer(delay, self._start_with_retry)
                retry_timer.daemon = True
                retry_timer.start()
            else:
                logger.error(
                    f"[Start] FAILED after {MAX_RECONNECT_ATTEMPTS} attempts. "
                    f"Manual restart required!"
                )

    def stop(self):
        """Stop the collector and cleanup"""
        if not self.running:
            return

        self.running = False
        self.flush_wakeup.set()
        self.health_wakeup.set()

        if self.flush_thread and self.flush_thread.is_alive():
            self.flush_thread.join(timeout=5)
        self.flush_thread = None

        if self.health_thread and self.health_thread.is_alive():
            self.health_thread.join(timeout=5)
        self.health_thread = None

        # Reset degraded mode state
        self.degraded_mode = False
        self.degraded_retry_count = 0
        self.next_degraded_retry_at = None

        # Flush remaining data
        self._flush_to_database()

        # Unsubscribe all
        for symbol in list(self.subscribed_symbols):
            self._unsubscribe_symbol(symbol)

        # Disconnect WebSocket
        self._cleanup_old_connection()
        logger.info("MarketFlowCollector stopped")

    def _ensure_worker_threads(self):
        """Ensure flush/health workers exist exactly once."""
        if not self.flush_thread or not self.flush_thread.is_alive():
            self.flush_wakeup.clear()
            self.flush_thread = threading.Thread(
                target=self._flush_worker_loop,
                daemon=True,
                name="market-flow-flush",
            )
            self.flush_thread.start()
            logger.info("[Collector] Flush worker started")

        if not self.health_thread or not self.health_thread.is_alive():
            self.health_wakeup.clear()
            self.health_thread = threading.Thread(
                target=self._health_worker_loop,
                daemon=True,
                name="market-flow-health",
            )
            self.health_thread.start()
            logger.info("[Collector] Health worker started")

    def _flush_worker_loop(self):
        """Persist data on 15-second boundaries using a single worker thread."""
        while self.running:
            now = time.time()
            next_boundary = (int(now) // AGGREGATION_WINDOW_SECONDS + 1) * AGGREGATION_WINDOW_SECONDS
            delay = max(0.1, next_boundary - now)
            if self.flush_wakeup.wait(delay):
                self.flush_wakeup.clear()
                continue
            self._flush_once()

    def _health_worker_loop(self):
        """Monitor connection health and degraded-mode retries using a single worker thread."""
        while self.running:
            wait_seconds = HEALTH_CHECK_INTERVAL_SECONDS
            if self.degraded_mode and self.next_degraded_retry_at:
                wait_seconds = max(1.0, min(wait_seconds, self.next_degraded_retry_at - time.time()))
            if self.health_wakeup.wait(wait_seconds):
                self.health_wakeup.clear()
                continue
            if not self.running:
                break
            if self.degraded_mode and self.next_degraded_retry_at and time.time() >= self.next_degraded_retry_at:
                self._reconnect()
            else:
                self._check_connection_health()

    def _check_connection_health(self):
        """Check if WebSocket data is stale and trigger reconnect if needed"""
        if self.is_reconnecting:
            logger.debug("Health check skipped - reconnection in progress")
            return

        if self.degraded_mode:
            return

        now = time.time()
        # Check l2book and asset_ctx freshness (these should update frequently)
        l2book_age = now - self.last_update_time["l2book"] if self.last_update_time["l2book"] > 0 else -1
        asset_ctx_age = now - self.last_update_time["asset_ctx"] if self.last_update_time["asset_ctx"] > 0 else -1
        trades_age = now - self.last_update_time["trades"] if self.last_update_time["trades"] > 0 else -1

        # Log current health status
        logger.info(
            f"[HealthCheck] Data freshness - l2book: {l2book_age:.0f}s, "
            f"asset_ctx: {asset_ctx_age:.0f}s, trades: {trades_age:.0f}s "
            f"(threshold: {DATA_STALE_THRESHOLD_SECONDS}s)"
        )

        # If both are stale, connection is likely dead
        if (self.last_update_time["l2book"] > 0 and l2book_age > DATA_STALE_THRESHOLD_SECONDS and
            self.last_update_time["asset_ctx"] > 0 and asset_ctx_age > DATA_STALE_THRESHOLD_SECONDS):
            logger.warning(
                f"[HealthCheck] STALE DATA DETECTED! WebSocket likely disconnected. "
                f"l2book: {l2book_age:.0f}s ago, asset_ctx: {asset_ctx_age:.0f}s ago. "
                f"Initiating reconnect..."
            )
            self._reconnect()

    def _reconnect(self):
        """Reconnect WebSocket with exponential backoff, then degraded mode"""
        with self.reconnect_lock:
            if self.is_reconnecting:
                logger.debug("[Reconnect] Already reconnecting, skipping")
                return
            self.is_reconnecting = True

        try:
            # Check if we should enter or continue degraded mode
            if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                if not self.degraded_mode:
                    # First time entering degraded mode
                    self.degraded_mode = True
                    self.degraded_retry_count = 0
                    logger.warning(
                        f"[Reconnect] Normal retries exhausted ({MAX_RECONNECT_ATTEMPTS}). "
                        f"Entering DEGRADED MODE - will retry every "
                        f"{DEGRADED_MODE_RETRY_INTERVAL_SECONDS}s indefinitely."
                    )

                self.degraded_retry_count += 1
                self.next_degraded_retry_at = time.time() + DEGRADED_MODE_RETRY_INTERVAL_SECONDS
                # Log every DEGRADED_MODE_LOG_INTERVAL attempts
                if self.degraded_retry_count % DEGRADED_MODE_LOG_INTERVAL == 1:
                    logger.warning(
                        f"[Reconnect] DEGRADED MODE attempt #{self.degraded_retry_count} "
                        f"(logging every {DEGRADED_MODE_LOG_INTERVAL} attempts)"
                    )
            else:
                # Normal mode with exponential backoff
                self.reconnect_attempts += 1
                delay = RECONNECT_BASE_DELAY_SECONDS * (2 ** (self.reconnect_attempts - 1))
                logger.warning(
                    f"[Reconnect] Attempt {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} "
                    f"starting after {delay}s delay..."
                )
                time.sleep(delay)

            # Save current symbols (use _pending_symbols as fallback)
            symbols_to_restore = list(self.subscribed_symbols) if self.subscribed_symbols else \
                                 getattr(self, '_pending_symbols', [])
            logger.info(f"[Reconnect] Will restore {len(symbols_to_restore)} symbols")

            # Disconnect old WebSocket and clean up
            self._cleanup_old_connection()

            # Create new Info client
            logger.info("[Reconnect] Creating new Hyperliquid Info client...")
            base_url = "https://api.hyperliquid.xyz"
            self.info = self._create_info_client(base_url)
            logger.info("[Reconnect] New Info client created")

            # Resubscribe to all symbols
            for symbol in symbols_to_restore:
                self._subscribe_symbol(symbol)

            # SUCCESS - reset all reconnection state
            self.reconnect_attempts = 0
            self.degraded_mode = False
            self.degraded_retry_count = 0
            self.next_degraded_retry_at = None
            now = time.time()
            self.last_update_time["l2book"] = now
            self.last_update_time["asset_ctx"] = now
            self.last_update_time["trades"] = now

            self.flush_wakeup.set()
            self.health_wakeup.set()

            logger.warning(
                f"[Reconnect] SUCCESS! Resubscribed to {len(symbols_to_restore)} symbols. "
                f"Data collection resumed."
            )

        except Exception as e:
            logger.error(f"Reconnect failed: {e}", exc_info=True)
            # Ensure info is None on failure to avoid using corrupted object
            self.info = None
            if self.degraded_mode and self.next_degraded_retry_at is None:
                self.next_degraded_retry_at = time.time() + DEGRADED_MODE_RETRY_INTERVAL_SECONDS
        finally:
            self.is_reconnecting = False

    def _cleanup_old_connection(self):
        """Clean up old WebSocket connection and subscription state"""
        if self.info and self.info.ws_manager:
            ws_manager = self.info.ws_manager
            try:
                self.info.disconnect_websocket()
                logger.info("[Reconnect] Old WebSocket disconnected")
            except Exception as e:
                logger.warning(f"[Reconnect] Error disconnecting old websocket: {e}")
            try:
                ws_manager.join(timeout=5)
                if ws_manager.is_alive():
                    logger.warning(
                        "[Reconnect] Old WebSocket manager did not exit cleanly; "
                        "threads=%s symbols=%s",
                        len(threading.enumerate()),
                        list(self.subscribed_symbols),
                    )
            except Exception as e:
                logger.warning(f"[Reconnect] Error joining old websocket manager: {e}")
        self.info = None
        self.subscribed_symbols = []
        self.subscription_ids.clear()
