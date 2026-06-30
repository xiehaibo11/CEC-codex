"""Flush worker and database persistence for aggregated market flow data."""

import json
import time
import logging
import threading
from decimal import Decimal

from services.market_flow_collector.constants import (
    AGGREGATION_WINDOW_SECONDS,
    DATA_STALE_THRESHOLD_SECONDS,
)

logger = logging.getLogger(__name__)


class MarketFlowFlushMixin:
    """Window flush orchestration and per-table persistence."""

    def _flush_once(self):
        """Run at most one flush at a time and emit diagnostics for abnormal delays."""
        if not self.flush_in_progress.acquire(blocking=False):
            if self.active_flush_started_at:
                logger.warning(
                    "[Flush] Previous flush still running; skipping this window. "
                    "duration=%.2fs threads=%s symbols=%s",
                    time.time() - self.active_flush_started_at,
                    len(threading.enumerate()),
                    list(self.subscribed_symbols),
                )
            return

        self.active_flush_started_at = time.time()
        try:
            self._flush_to_database()
            duration = time.time() - self.active_flush_started_at
            if duration > AGGREGATION_WINDOW_SECONDS:
                logger.warning(
                    "[Flush] Slow flush detected: duration=%.2fs threads=%s symbols=%s",
                    duration,
                    len(threading.enumerate()),
                    list(self.subscribed_symbols),
                )
        finally:
            self.active_flush_started_at = None
            self.flush_in_progress.release()

    def _flush_to_database(self):
        """Flush all buffered data to database"""
        if not self.subscribed_symbols:
            return

        timestamp_ms = int(time.time() * 1000)
        # Align to 15-second boundary
        timestamp_ms = (timestamp_ms // (AGGREGATION_WINDOW_SECONDS * 1000)) * (AGGREGATION_WINDOW_SECONDS * 1000)

        try:
            from database.connection import SessionLocal
            from database.models import MarketTradesAggregated, MarketOrderbookSnapshots, MarketAssetMetrics

            db = SessionLocal()
            try:
                for symbol in self.subscribed_symbols:
                    self._flush_trades(db, symbol, timestamp_ms)
                    self._flush_orderbook(db, symbol, timestamp_ms)
                    self._flush_asset_metrics(db, symbol, timestamp_ms)

                db.commit()
                logger.debug(f"Flushed market flow data for {len(self.subscribed_symbols)} symbols")

                # Run signal detection after data flush
                self._run_signal_detection()

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to flush market flow data: {e}")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Database error in flush: {e}")

    def _run_signal_detection(self):
        """Run signal detection for all subscribed symbols (Hyperliquid only)"""
        try:
            from services.signal_detection_service import signal_detection_service

            for symbol in self.subscribed_symbols:
                # Build market data context for signal detection
                market_data = {
                    "asset_ctx": self.latest_asset_ctx.get(symbol, {}),
                    "orderbook": self.latest_orderbook.get(symbol, {}),
                }

                # Detect signals for Hyperliquid pools only
                triggered = signal_detection_service.detect_signals(
                    symbol, market_data, exchange="hyperliquid"
                )
                if triggered:
                    logger.info(f"Pools triggered for {symbol}: {[p['pool_name'] for p in triggered]}")

        except Exception as e:
            logger.error(f"Error in signal detection: {e}", exc_info=True)

    def _flush_trades(self, db, symbol: str, timestamp_ms: int):
        """Flush trade buffer for a symbol using native PostgreSQL upsert"""
        with self.buffer_lock:
            buffer = self.trade_buffers.get(symbol)
            if not buffer or buffer.total_volume == 0:
                return

            vwap = None
            if buffer.total_volume > 0:
                vwap = buffer.total_notional / buffer.total_volume

            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from database.models import MarketTradesAggregated

            values = dict(
                exchange="hyperliquid", symbol=symbol, timestamp=timestamp_ms,
                taker_buy_volume=buffer.taker_buy_volume,
                taker_sell_volume=buffer.taker_sell_volume,
                taker_buy_count=buffer.taker_buy_count,
                taker_sell_count=buffer.taker_sell_count,
                taker_buy_notional=buffer.taker_buy_notional,
                taker_sell_notional=buffer.taker_sell_notional,
                large_buy_notional=buffer.large_buy_notional,
                large_sell_notional=buffer.large_sell_notional,
                large_buy_count=buffer.large_buy_count,
                large_sell_count=buffer.large_sell_count,
                vwap=vwap, high_price=buffer.high_price, low_price=buffer.low_price,
            )
            update_cols = {k: v for k, v in values.items() if k not in ("exchange", "symbol", "timestamp")}
            stmt = pg_insert(MarketTradesAggregated).values(**values).on_conflict_do_update(
                index_elements=["exchange", "symbol", "timestamp"],
                set_=update_cols,
            )
            db.execute(stmt)
            buffer.reset()

    def _flush_orderbook(self, db, symbol: str, timestamp_ms: int):
        """Flush orderbook snapshot for a symbol using native PostgreSQL upsert"""
        # Skip if data is stale (WebSocket disconnected)
        l2book_age = time.time() - self.last_update_time["l2book"]
        if self.last_update_time["l2book"] > 0 and l2book_age > DATA_STALE_THRESHOLD_SECONDS:
            logger.warning(f"[StaleData] Skipping orderbook flush for {symbol} - data is {l2book_age:.0f}s old")
            return

        data = self.latest_orderbook.get(symbol)
        if not data:
            return

        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from database.models import MarketOrderbookSnapshots

            levels = data.get("levels", [[], []])
            bids = levels[0] if len(levels) > 0 else []
            asks = levels[1] if len(levels) > 1 else []

            best_bid = Decimal(bids[0]["px"]) if bids else None
            best_ask = Decimal(asks[0]["px"]) if asks else None
            spread = (best_ask - best_bid) if (best_bid and best_ask) else None

            bid_depth_5 = sum(Decimal(b["sz"]) for b in bids[:5])
            ask_depth_5 = sum(Decimal(a["sz"]) for a in asks[:5])
            bid_depth_10 = sum(Decimal(b["sz"]) for b in bids[:10])
            ask_depth_10 = sum(Decimal(a["sz"]) for a in asks[:10])

            bid_orders = sum(b.get("n", 1) for b in bids)
            ask_orders = sum(a.get("n", 1) for a in asks)

            values = dict(
                exchange="hyperliquid", symbol=symbol, timestamp=timestamp_ms,
                best_bid=best_bid, best_ask=best_ask, spread=spread,
                bid_depth_5=bid_depth_5, ask_depth_5=ask_depth_5,
                bid_depth_10=bid_depth_10, ask_depth_10=ask_depth_10,
                bid_orders_count=bid_orders, ask_orders_count=ask_orders,
                raw_levels=json.dumps(levels),
            )
            update_cols = {k: v for k, v in values.items() if k not in ("exchange", "symbol", "timestamp")}
            stmt = pg_insert(MarketOrderbookSnapshots).values(**values).on_conflict_do_update(
                index_elements=["exchange", "symbol", "timestamp"],
                set_=update_cols,
            )
            db.execute(stmt)

        except Exception as e:
            logger.error(f"Error flushing orderbook for {symbol}: {e}")

    def _flush_asset_metrics(self, db, symbol: str, timestamp_ms: int):
        """Flush asset metrics for a symbol using native PostgreSQL upsert"""
        # Skip if data is stale (WebSocket disconnected)
        asset_ctx_age = time.time() - self.last_update_time["asset_ctx"]
        if self.last_update_time["asset_ctx"] > 0 and asset_ctx_age > DATA_STALE_THRESHOLD_SECONDS:
            logger.warning(f"[StaleData] Skipping asset metrics flush for {symbol} - data is {asset_ctx_age:.0f}s old")
            return

        data = self.latest_asset_ctx.get(symbol)
        if not data:
            return

        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from database.models import MarketAssetMetrics

            ctx = data.get("ctx", {})
            values = dict(
                exchange="hyperliquid", symbol=symbol, timestamp=timestamp_ms,
                open_interest=Decimal(ctx["openInterest"]) if ctx.get("openInterest") else None,
                funding_rate=Decimal(ctx["funding"]) if ctx.get("funding") else None,
                mark_price=Decimal(ctx["markPx"]) if ctx.get("markPx") else None,
                oracle_price=Decimal(ctx["oraclePx"]) if ctx.get("oraclePx") else None,
                mid_price=Decimal(ctx["midPx"]) if ctx.get("midPx") else None,
                premium=Decimal(ctx["premium"]) if ctx.get("premium") else None,
                day_notional_volume=Decimal(ctx["dayNtlVlm"]) if ctx.get("dayNtlVlm") else None,
            )
            update_cols = {k: v for k, v in values.items() if k not in ("exchange", "symbol", "timestamp")}
            stmt = pg_insert(MarketAssetMetrics).values(**values).on_conflict_do_update(
                index_elements=["exchange", "symbol", "timestamp"],
                set_=update_cols,
            )
            db.execute(stmt)

        except Exception as e:
            logger.error(f"Error flushing asset metrics for {symbol}: {e}")
