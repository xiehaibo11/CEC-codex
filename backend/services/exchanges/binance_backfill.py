"""
Binance historical data backfill service
"""

import asyncio
import math
import logging
import time
from typing import Optional

from database.connection import SessionLocal
from database.models import BinanceBackfillTask, SystemConfig
from .binance_adapter import BinanceAdapter
from .binance_constants import BINANCE_KLINE_INTERVAL_SECONDS, BINANCE_KLINE_INTERVALS
from .data_persistence import ExchangeDataPersistence

logger = logging.getLogger(__name__)

# Backfill limits
KLINE_BACKFILL_LIMIT = 1500  # Per period
KLINE_BACKFILL_DAYS_DEFAULT = 365
KLINE_PAGE_DELAY_SECONDS = 0.35
KLINE_PERIODS = BINANCE_KLINE_INTERVALS
SPAN_KLINE_PERIODS = {"3d", "1w", "1M"}
OI_BACKFILL_DAYS = 30
FUNDING_BACKFILL_DAYS = 365
SENTIMENT_BACKFILL_DAYS = 30
BINANCE_RETENTION_KEY = "binance_retention_days"


class BinanceBackfillService:
    """Service for backfilling Binance historical data"""

    def __init__(self):
        self.adapter = BinanceAdapter()
        self.running = False
        self.current_task_id: Optional[int] = None

    async def start_backfill(self, task_id: int):
        """Start backfill task"""
        if self.running:
            logger.warning("Backfill already running")
            return False

        self.running = True
        self.current_task_id = task_id

        try:
            await self._process_task(task_id)
        finally:
            self.running = False
            self.current_task_id = None

        return True

    async def _process_task(self, task_id: int):
        """Process a backfill task"""
        db = SessionLocal()
        try:
            task = db.query(BinanceBackfillTask).filter(
                BinanceBackfillTask.id == task_id
            ).first()

            if not task:
                logger.error(f"Backfill task {task_id} not found")
                return

            task.status = "running"
            task.progress = 0
            db.commit()

            symbols = task.symbols.split(",") if task.symbols else ["BTC"]
            backfill_days = self._get_backfill_days(db)
            end_time_ms = int(time.time() * 1000)
            start_time_ms = end_time_ms - (backfill_days * 24 * 60 * 60 * 1000)

            # Steps: (klines x periods) + OI + Funding + Sentiment per symbol
            total_kline_pages = self._estimate_kline_pages(backfill_days)
            total_steps = len(symbols) * (total_kline_pages + 3)
            current_step = 0

            persistence = ExchangeDataPersistence(db)

            def update_progress(steps: int = 1):
                nonlocal current_step
                current_step += steps
                task.progress = min(99, int(current_step / total_steps * 100))
                db.commit()

            for symbol in symbols:
                # 1. Backfill K-lines for each period
                for period in KLINE_PERIODS:
                    try:
                        period_start_time_ms = self._start_time_for_period(start_time_ms, period)
                        await self._backfill_klines(
                            symbol,
                            period,
                            persistence,
                            period_start_time_ms,
                            end_time_ms,
                            backfill_days,
                            update_progress,
                        )
                    except Exception as e:
                        logger.error(f"Kline backfill failed for {symbol}/{period}: {e}")

                # 2. Backfill OI (30 days)
                try:
                    await self._backfill_oi(symbol, persistence)
                except Exception as e:
                    logger.error(f"OI backfill failed for {symbol}: {e}")
                update_progress()
                await asyncio.sleep(3)

                # 3. Backfill Funding Rate (365 days)
                try:
                    await self._backfill_funding(symbol, persistence)
                except Exception as e:
                    logger.error(f"Funding backfill failed for {symbol}: {e}")
                update_progress()
                await asyncio.sleep(3)

                # 4. Backfill Sentiment (30 days)
                try:
                    await self._backfill_sentiment(symbol, persistence)
                except Exception as e:
                    logger.error(f"Sentiment backfill failed for {symbol}: {e}")
                update_progress()
                await asyncio.sleep(3)

            task.status = "completed"
            task.progress = 100
            db.commit()
            logger.info(f"Backfill task {task_id} completed")

        except Exception as e:
            logger.error(f"Backfill task {task_id} failed: {e}")
            task = db.query(BinanceBackfillTask).filter(
                BinanceBackfillTask.id == task_id
            ).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                db.commit()
        finally:
            db.close()

    def _get_backfill_days(self, db) -> int:
        config = db.query(SystemConfig).filter(SystemConfig.key == BINANCE_RETENTION_KEY).first()
        if config and config.value:
            try:
                return max(7, min(730, int(config.value)))
            except ValueError:
                logger.warning("Invalid Binance retention days config: %s", config.value)
        return KLINE_BACKFILL_DAYS_DEFAULT

    def _start_time_for_period(self, start_time_ms: int, period: str) -> int:
        """Start span periods one interval earlier to cover retention-window edges."""
        if period not in SPAN_KLINE_PERIODS:
            return start_time_ms
        interval_seconds = BINANCE_KLINE_INTERVAL_SECONDS.get(period, 0)
        return max(0, start_time_ms - interval_seconds * 1000)

    def _estimate_kline_pages(self, backfill_days: int) -> int:
        total_pages = 0
        total_seconds = backfill_days * 24 * 60 * 60
        for period in KLINE_PERIODS:
            interval_seconds = BINANCE_KLINE_INTERVAL_SECONDS.get(period, 60)
            expected_records = max(1, math.ceil(total_seconds / interval_seconds))
            total_pages += max(1, math.ceil(expected_records / KLINE_BACKFILL_LIMIT))
        return total_pages

    async def _backfill_klines(
        self,
        symbol: str,
        period: str,
        persistence: ExchangeDataPersistence,
        start_time_ms: int,
        end_time_ms: int,
        backfill_days: int,
        update_progress,
    ):
        """Backfill K-line data for a period using Binance time-range pagination."""
        logger.info(
            "Backfilling klines for %s/%s (%s days, %s to %s)",
            symbol,
            period,
            backfill_days,
            start_time_ms,
            end_time_ms,
        )
        current_start_ms = start_time_ms
        total_upserted = 0
        page = 0

        while current_start_ms <= end_time_ms:
            klines = self.adapter.fetch_klines(
                symbol,
                period,
                limit=KLINE_BACKFILL_LIMIT,
                start_time=current_start_ms,
                end_time=end_time_ms,
            )
            if not klines:
                if page == 0:
                    update_progress()
                break

            page += 1
            result = persistence.upsert_klines_bulk(klines)
            if period == "1m":
                persistence.upsert_taker_volumes_from_klines_bulk(klines)
            total_upserted += result.get("upserted", 0)
            update_progress()

            last_open_ms = klines[-1].timestamp * 1000
            next_start_ms = last_open_ms + 1
            if len(klines) < KLINE_BACKFILL_LIMIT or next_start_ms <= current_start_ms:
                break

            current_start_ms = next_start_ms
            await asyncio.sleep(KLINE_PAGE_DELAY_SECONDS)

        logger.info(
            "Klines backfill %s/%s completed: pages=%s, upserted=%s",
            symbol,
            period,
            page,
            total_upserted,
        )

    async def _backfill_oi(self, symbol: str, persistence: ExchangeDataPersistence):
        """
        Backfill Open Interest history - DISABLED

        Binance OI history API only supports 5m granularity, but real-time collection
        now uses 1m granularity. Mixing 5m historical data with 1m real-time data
        would cause timestamp misalignment and data pollution.

        OI data will be accumulated from real-time collection going forward.
        """
        logger.info(f"OI backfill SKIPPED for {symbol} - using 1m real-time collection instead of 5m history")

    async def _backfill_funding(self, symbol: str, persistence: ExchangeDataPersistence):
        """Backfill Funding Rate history (365 days)"""
        logger.info(f"Backfilling funding for {symbol} ({FUNDING_BACKFILL_DAYS} days)")
        all_funding = []
        end_time = int(time.time() * 1000)
        start_time = end_time - (FUNDING_BACKFILL_DAYS * 24 * 60 * 60 * 1000)

        current_end = end_time
        while current_end > start_time:
            funding_list = self.adapter.fetch_funding_history(
                symbol, limit=1000, end_time=current_end
            )
            if not funding_list:
                break
            all_funding.extend(funding_list)
            current_end = min(f.timestamp for f in funding_list) - 1
            await asyncio.sleep(0.5)

        if all_funding:
            result = persistence.save_funding_rate_batch(all_funding)
            logger.info(f"Funding backfill {symbol}: {result}, total {len(all_funding)} records")

    async def _backfill_sentiment(self, symbol: str, persistence: ExchangeDataPersistence):
        """Backfill Long/Short ratio history (30 days)"""
        logger.info(f"Backfilling sentiment for {symbol} ({SENTIMENT_BACKFILL_DAYS} days)")
        all_sentiment = []
        end_time = int(time.time() * 1000)
        start_time = end_time - (SENTIMENT_BACKFILL_DAYS * 24 * 60 * 60 * 1000)

        current_end = end_time
        while current_end > start_time:
            sentiment_list = self.adapter.fetch_sentiment_history(
                symbol, "5m", limit=500, end_time=current_end
            )
            if not sentiment_list:
                break
            all_sentiment.extend(sentiment_list)
            current_end = min(s.timestamp for s in sentiment_list) - 1
            await asyncio.sleep(0.5)

        if all_sentiment:
            result = persistence.save_sentiment_batch(all_sentiment)
            logger.info(f"Sentiment backfill {symbol}: {result}, total {len(all_sentiment)} records")


# Singleton instance
binance_backfill_service = BinanceBackfillService()
