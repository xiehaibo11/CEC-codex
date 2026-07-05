"""HiBT data backfill service.

Mirrors :mod:`services.exchanges.hyperliquid_backfill`: pulls recent candles
from HiBT's public candle endpoint for each watchlist symbol across a few
periods and upserts them into ``crypto_klines`` so the HiBT data tab's coverage
grows on demand. HiBT's candle endpoint caps at 500 rows per request, so this
is a "recent window" backfill rather than deep history. HiBT taker flow comes
from the public deals endpoint and only covers the latest visible trade window.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from database.connection import SessionLocal
from database.models import HibtBackfillTask, SystemConfig
from services.exchanges.base_adapter import UnifiedKline
from services.exchanges.binance_constants import BINANCE_KLINE_INTERVALS
from services.exchanges.data_persistence import ExchangeDataPersistence
from services.hibt_market_data import fetch_hibt_deals, fetch_hibt_klines
from services.hibt_trading_client import HibtTradingClient

logger = logging.getLogger(__name__)

# HiBT candle endpoint returns at most 500 rows per request.
KLINE_BACKFILL_LIMIT = 500
# Multiple periods for broader coverage; these are the periods documented by
# HiBT's public candle endpoint.
KLINE_PERIODS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"]
DERIVED_KLINE_PERIODS = {
    "3m": ("1m", 3 * 60),
    "5m": ("1m", 5 * 60),
    "15m": ("1m", 15 * 60),
    "30m": ("1m", 30 * 60),
    "1h": ("1m", 60 * 60),
    "2h": ("1m", 2 * 60 * 60),
    "4h": ("1m", 4 * 60 * 60),
    "6h": ("1m", 6 * 60 * 60),
    "8h": ("1m", 8 * 60 * 60),
    "12h": ("1m", 12 * 60 * 60),
    "3d": ("1d", 3 * 24 * 60 * 60),
    "1M": ("1d", None),
    "1w": ("1d", 7 * 24 * 60 * 60),
}
ALL_KLINE_PERIODS = BINANCE_KLINE_INTERVALS
KLINE_INTERVAL_SECONDS = {
    "1m": 60,
    "3m": 3 * 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
    "6h": 6 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "1d": 24 * 60 * 60,
    "3d": 3 * 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}
# Seconds to wait between requests to stay well under HiBT's rate limits.
_REQUEST_SPACING_SECONDS = 1
_PAGE_SPACING_SECONDS = 0.05
DEFAULT_RETENTION_DAYS = 365
HIBT_RETENTION_KEY = "hibt_retention_days"


class HibtBackfillService:
    """Service for backfilling HiBT K-line and latest market-flow data."""

    def __init__(self):
        self.running = False
        self.current_task_id: Optional[int] = None

    async def start_backfill(self, task_id: int) -> bool:
        """Start a backfill task; no-op if one is already running in-process."""
        if self.running:
            logger.warning("[HiBT] Backfill already running")
            return False

        self.running = True
        self.current_task_id = task_id
        try:
            await self._process_task(task_id)
        finally:
            self.running = False
            self.current_task_id = None
        return True

    async def _process_task(self, task_id: int) -> None:
        db = SessionLocal()
        try:
            task = db.query(HibtBackfillTask).filter(HibtBackfillTask.id == task_id).first()
            if not task:
                logger.error("[HiBT] Backfill task %s not found", task_id)
                return

            task.status = "running"
            task.progress = 0
            db.commit()

            symbols = task.symbols.split(",") if task.symbols else ["BTC"]
            retention_days = self._get_retention_days(db)
            total_steps = len(symbols) * (len(KLINE_PERIODS) + len(DERIVED_KLINE_PERIODS) + 1)
            current_step = 0

            for symbol in symbols:
                try:
                    await asyncio.to_thread(self._backfill_market_flow, symbol)
                except Exception as exc:  # noqa: BLE001 - one symbol must not kill the task
                    logger.error("[HiBT] Market-flow backfill failed for %s: %s", symbol, exc)

                current_step += 1
                task.progress = int(current_step / total_steps * 100)
                db.commit()
                await asyncio.sleep(_REQUEST_SPACING_SECONDS)

                for period in KLINE_PERIODS:
                    try:
                        await asyncio.to_thread(self._backfill_klines, symbol, period, retention_days)
                    except Exception as exc:  # noqa: BLE001 - one pair must not kill the task
                        logger.error("[HiBT] Kline backfill failed for %s/%s: %s", symbol, period, exc)

                    current_step += 1
                    task.progress = int(current_step / total_steps * 100)
                    db.commit()
                    await asyncio.sleep(_REQUEST_SPACING_SECONDS)

                for period, (source_period, period_seconds) in DERIVED_KLINE_PERIODS.items():
                    try:
                        await asyncio.to_thread(
                            self._derive_klines_from_existing_period,
                            symbol,
                            period,
                            source_period,
                            period_seconds,
                            retention_days,
                        )
                    except Exception as exc:  # noqa: BLE001 - one derived period must not kill the task
                        logger.error("[HiBT] Derived Kline backfill failed for %s/%s: %s", symbol, period, exc)

                    current_step += 1
                    task.progress = int(current_step / total_steps * 100)
                    db.commit()
                    await asyncio.sleep(_REQUEST_SPACING_SECONDS)

            task.status = "completed"
            task.progress = 100
            db.commit()
            logger.info("[HiBT] Backfill task %s completed", task_id)

        except Exception as exc:  # noqa: BLE001 - surface failure on the task row
            logger.error("[HiBT] Backfill task %s failed: %s", task_id, exc)
            task = db.query(HibtBackfillTask).filter(HibtBackfillTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(exc)
                db.commit()
        finally:
            db.close()

    def _get_retention_days(self, db) -> int:
        """Read HiBT retention days without depending on API route helpers."""
        try:
            config = db.query(SystemConfig).filter(SystemConfig.key == HIBT_RETENTION_KEY).first()
            value = getattr(config, "value", None)
            if value:
                return int(value)
        except Exception:
            pass
        return DEFAULT_RETENTION_DAYS

    def _backfill_klines(self, symbol: str, period: str, retention_days: float = DEFAULT_RETENTION_DAYS) -> None:
        """Fetch and persist one symbol/period over the retention window."""
        interval_seconds = KLINE_INTERVAL_SECONDS.get(period)
        if not interval_seconds:
            logger.warning("[HiBT] Unsupported K-line period for backfill: %s", period)
            return

        now_ms = int(time.time() * 1000)
        interval_ms = interval_seconds * 1000
        start_ms = now_ms - int(float(retention_days) * 24 * 60 * 60 * 1000)
        cursor_ms = max(0, (start_ms // interval_ms) * interval_ms)
        end_ms = (now_ms // interval_ms) * interval_ms
        window_ms = interval_ms * KLINE_BACKFILL_LIMIT

        logger.info(
            "[HiBT] Backfilling %s/%s (%s days, %s to %s, page_limit=%s)",
            symbol,
            period,
            retention_days,
            cursor_ms,
            end_ms,
            KLINE_BACKFILL_LIMIT,
        )

        total_saved = 0
        db = None
        client = HibtTradingClient(access_key="", secret_key="")
        try:
            persistence = None
            while cursor_ms < end_ms:
                page_end_ms = min(cursor_ms + window_ms, end_ms)
                klines = fetch_hibt_klines(
                    symbol,
                    period,
                    count=KLINE_BACKFILL_LIMIT,
                    start=cursor_ms,
                    end=page_end_ms,
                    client=client,
                )
                if klines:
                    if persistence is None:
                        db = SessionLocal()
                        persistence = ExchangeDataPersistence(db)
                    persistence.save_klines(klines, environment="mainnet")
                    if period == "1m":
                        persistence.upsert_taker_volume_proxy_from_klines_bulk(klines, bucket_seconds=60)
                    total_saved += len(klines)
                cursor_ms = page_end_ms
                if _PAGE_SPACING_SECONDS > 0:
                    time.sleep(_PAGE_SPACING_SECONDS)

            if total_saved == 0:
                logger.warning("[HiBT] No klines returned for %s/%s", symbol, period)
                return
            logger.info("[HiBT] Klines backfill %s/%s: saved %s records", symbol, period, total_saved)
        finally:
            if db is not None:
                db.close()

    def _derive_klines_from_existing_period(
        self,
        symbol: str,
        target_period: str,
        source_period: str,
        target_seconds: int | None,
        retention_days: float = DEFAULT_RETENTION_DAYS,
    ) -> None:
        """Derive HiBT coverage periods unsupported by the public candle API."""
        now_s = int(time.time())
        start_s = now_s - int(float(retention_days) * 24 * 60 * 60)
        db = SessionLocal()
        try:
            from sqlalchemy import text

            rows = db.execute(text("""
                SELECT timestamp, open_price, high_price, low_price, close_price, volume, amount
                FROM crypto_klines
                WHERE exchange = 'hibt'
                  AND symbol = :symbol
                  AND period = :source_period
                  AND timestamp >= :start_ts
                  AND environment = 'mainnet'
                ORDER BY timestamp
            """), {"symbol": symbol, "source_period": source_period, "start_ts": start_s}).mappings().all()
            if not rows:
                logger.warning(
                    "[HiBT] No source klines for deriving %s/%s from %s",
                    symbol,
                    target_period,
                    source_period,
                )
                return

            buckets = {}
            for row in rows:
                ts = int(row["timestamp"])
                if target_period == "1M":
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    bucket_ts = int(datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp())
                else:
                    bucket_ts = (ts // int(target_seconds or 1)) * int(target_seconds or 1)

                bucket = buckets.setdefault(
                    bucket_ts,
                    {
                        "first_ts": ts,
                        "last_ts": ts,
                        "open_price": Decimal(str(row["open_price"])),
                        "high_price": Decimal(str(row["high_price"])),
                        "low_price": Decimal(str(row["low_price"])),
                        "close_price": Decimal(str(row["close_price"])),
                        "volume": Decimal(str(row["volume"] or 0)),
                        "amount": Decimal(str(row["amount"] or 0)),
                    },
                )
                high = Decimal(str(row["high_price"]))
                low = Decimal(str(row["low_price"]))
                if high > bucket["high_price"]:
                    bucket["high_price"] = high
                if low < bucket["low_price"]:
                    bucket["low_price"] = low
                if ts < bucket["first_ts"]:
                    bucket["first_ts"] = ts
                    bucket["open_price"] = Decimal(str(row["open_price"]))
                if ts >= bucket["last_ts"]:
                    bucket["last_ts"] = ts
                    bucket["close_price"] = Decimal(str(row["close_price"]))
                # setdefault row already added first row; skip double-adding it
                if ts != bucket["first_ts"]:
                    bucket["volume"] += Decimal(str(row["volume"] or 0))
                    bucket["amount"] += Decimal(str(row["amount"] or 0))

            klines = [
                UnifiedKline(
                    exchange="hibt",
                    symbol=symbol,
                    interval=target_period,
                    timestamp=bucket_ts,
                    open_price=bucket["open_price"],
                    high_price=bucket["high_price"],
                    low_price=bucket["low_price"],
                    close_price=bucket["close_price"],
                    volume=bucket["volume"],
                    quote_volume=bucket["amount"],
                )
                for bucket_ts, bucket in sorted(buckets.items())
            ]
            ExchangeDataPersistence(db).insert_klines_ignore_conflicts_bulk(klines, environment="mainnet")
            logger.info(
                "[HiBT] Derived Klines %s/%s from %s: saved %s records",
                symbol,
                target_period,
                source_period,
                len(klines),
            )
        finally:
            db.close()

    def _backfill_market_flow(self, symbol: str) -> None:
        """Fetch and persist the latest HiBT public deal window."""
        logger.info("[HiBT] Backfilling latest market flow for %s", symbol)
        trades = fetch_hibt_deals(symbol)
        if not trades:
            logger.warning("[HiBT] No public deals returned for %s", symbol)
            return
        db = SessionLocal()
        try:
            result = ExchangeDataPersistence(db).upsert_taker_trades_bulk(trades, bucket_seconds=15)
            logger.info(
                "[HiBT] Market-flow backfill %s: upserted %s buckets from %s trades",
                symbol,
                result.get("upserted", 0),
                len(trades),
            )
        finally:
            db.close()


# Singleton instance
hibt_backfill_service = HibtBackfillService()
