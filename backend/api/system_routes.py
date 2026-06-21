"""System configuration and data management API routes"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.connection import get_db
from database.models import SystemConfig
from services.exchanges.binance_constants import (
    BINANCE_KLINE_INTERVAL_SECONDS,
    BINANCE_KLINE_INTERVALS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])

# Config keys
HYPERLIQUID_RETENTION_KEY = "hyperliquid_retention_days"
BINANCE_RETENTION_KEY = "binance_retention_days"
DEFAULT_RETENTION_DAYS = 365


class RetentionDaysRequest(BaseModel):
    days: int
    exchange: str = "hyperliquid"


class RetentionDaysResponse(BaseModel):
    days: int
    exchange: str = "hyperliquid"


def get_retention_key(exchange: str) -> str:
    """Get the config key for a specific exchange"""
    if exchange == "binance":
        return BINANCE_RETENTION_KEY
    return HYPERLIQUID_RETENTION_KEY


def get_retention_days(db: Session, exchange: str = "hyperliquid") -> int:
    """Get configured retention days from SystemConfig for specific exchange"""
    key = get_retention_key(exchange)
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config and config.value:
        try:
            return int(config.value)
        except ValueError:
            pass
    return DEFAULT_RETENTION_DAYS


def set_retention_days(db: Session, days: int, exchange: str = "hyperliquid") -> int:
    """Set retention days in SystemConfig for specific exchange"""
    key = get_retention_key(exchange)
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config:
        config.value = str(days)
    else:
        config = SystemConfig(
            key=key,
            value=str(days),
            description=f"{exchange.capitalize()} market data retention period in days"
        )
        db.add(config)
    db.commit()
    return days


def get_expected_kline_records_per_day(period: str) -> int:
    """Return the expected number of K-line records per calendar day."""
    interval_seconds = BINANCE_KLINE_INTERVAL_SECONDS.get(period)
    if not interval_seconds:
        return 24
    if interval_seconds >= 24 * 60 * 60:
        return 1
    return max(1, (24 * 60 * 60) // interval_seconds)


@router.get("/storage-stats")
def get_storage_stats(exchange: str = "hyperliquid", db: Session = Depends(get_db)):
    """Get storage statistics for market flow data tables by exchange"""
    try:
        # Tables with exchange column
        tables_with_exchange = [
            'market_trades_aggregated',
            'market_asset_metrics',
            'market_orderbook_snapshots',
            'crypto_klines'
        ]
        if exchange == "binance":
            tables_with_exchange.append('market_sentiment_metrics')

        tables = {}
        total_bytes = 0

        for table_name in tables_with_exchange:
            try:
                # Get total table size (including indexes)
                size_query = text("""
                    SELECT pg_total_relation_size(relid) as total_bytes
                    FROM pg_catalog.pg_statio_user_tables
                    WHERE relname = :table_name
                """)
                table_size = db.execute(size_query, {"table_name": table_name}).scalar() or 0

                # Get row ratio for this exchange
                ratio_query = text(f"""
                    SELECT
                        COALESCE(
                            (SELECT COUNT(*)::float FROM {table_name} WHERE exchange = :exchange) /
                            NULLIF((SELECT COUNT(*)::float FROM {table_name}), 0),
                            0
                        )
                """)
                ratio = db.execute(ratio_query, {"exchange": exchange}).scalar() or 0

                # Calculate this exchange's share of the table
                exchange_bytes = int(table_size * ratio)
                tables[table_name] = round(exchange_bytes / (1024 * 1024), 1)
                total_bytes += exchange_bytes
            except Exception as e:
                logger.warning(f"Failed to get stats for {table_name}: {e}")
                tables[table_name] = 0

        total_mb = round(total_bytes / (1024 * 1024), 1)
        retention_days = get_retention_days(db, exchange)

        # Get symbol count and date range for estimation
        count_query = text("""
            SELECT
                COUNT(DISTINCT symbol) as symbol_count,
                MIN(timestamp) as min_ts,
                MAX(timestamp) as max_ts
            FROM market_trades_aggregated
            WHERE exchange = :exchange
        """)
        count_result = db.execute(count_query, {"exchange": exchange}).fetchone()
        symbol_count = count_result[0] or 1
        min_ts = count_result[1]
        max_ts = count_result[2]

        # Calculate per-symbol-per-day estimate
        if min_ts and max_ts and total_mb > 0:
            days_of_data = max((max_ts - min_ts) / (1000 * 86400), 1)
            per_symbol_per_day = total_mb / (symbol_count * days_of_data)
        else:
            per_symbol_per_day = 6.7  # fallback estimate

        return {
            "exchange": exchange,
            "total_size_mb": total_mb,
            "tables": tables,
            "retention_days": retention_days,
            "symbol_count": symbol_count,
            "estimated_per_symbol_per_day_mb": round(per_symbol_per_day, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-coverage")
def get_data_coverage(
    days: int = 30,
    symbol: Optional[str] = None,
    tz_offset: int = 0,
    exchange: str = "hyperliquid",
    data_type: str = "market_flow",
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get data coverage heatmap for market data.
    If symbol is provided, returns coverage for that symbol only.
    If symbol is not provided, returns list of available symbols.
    tz_offset: timezone offset in minutes (e.g., -480 for UTC+8)
    exchange: hyperliquid or binance
    data_type: market_flow or klines
    period: K-line period when data_type=klines
    """
    try:
        import time
        now_ts = int(time.time())

        if data_type not in {"market_flow", "klines"}:
            raise HTTPException(status_code=400, detail=f"Unsupported data_type: {data_type}")

        # Determine table and timestamp handling based on data_type
        # crypto_klines uses seconds, market_trades_aggregated uses milliseconds
        if data_type == "klines":
            table_name = "crypto_klines"
            start_ts = now_ts - (days * 24 * 60 * 60)  # seconds
            ts_divisor = 1  # already in seconds
        else:
            table_name = "market_trades_aggregated"
            start_ts = now_ts * 1000 - (days * 24 * 60 * 60 * 1000)  # milliseconds
            ts_divisor = 1000  # convert to seconds for to_timestamp

        is_span_kline_period = data_type == "klines" and period in {"3d", "1w", "1M"}
        span_lookback_seconds = 0
        if is_span_kline_period:
            span_lookback_seconds = 35 * 24 * 60 * 60 if period == "1M" else BINANCE_KLINE_INTERVAL_SECONDS[period]

        period_filter = ""
        base_params = {"start_ts": max(0, start_ts - span_lookback_seconds), "exchange": exchange}
        if data_type == "klines" and period:
            if exchange == "binance" and period not in BINANCE_KLINE_INTERVALS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported Binance K-line period: {period}",
                )
            period_filter = "AND period = :period"
            base_params["period"] = period

        # If no symbol specified, return available symbols list
        if not symbol:
            symbols_query = text(f"""
                SELECT DISTINCT symbol FROM {table_name}
                WHERE timestamp >= :start_ts AND exchange = :exchange {period_filter}
                ORDER BY symbol
            """)
            result = db.execute(symbols_query, base_params)
            symbols = [row[0] for row in result.fetchall()]
            return {
                "symbols": symbols,
                "exchange": exchange,
                "data_type": data_type,
                "period": period,
                "periods": BINANCE_KLINE_INTERVALS if exchange == "binance" and data_type == "klines" else [],
            }

        if data_type == "klines" and not period:
            raise HTTPException(status_code=400, detail="K-line coverage requires period")

        # Convert tz_offset from minutes to interval string
        offset_minutes = -tz_offset
        offset_interval = f"{offset_minutes} minutes"
        from datetime import timezone as tz
        local_offset = timedelta(minutes=offset_minutes)
        local_tz = tz(local_offset)
        end_date = datetime.now(local_tz).date()
        start_date = end_date - timedelta(days=days - 1)

        params = {
            "start_ts": start_ts,
            "query_start_ts": max(0, start_ts - span_lookback_seconds),
            "symbol": symbol.upper(),
            "tz_interval": offset_interval,
            "exchange": exchange,
            **({"period": period} if period_filter else {}),
        }

        if is_span_kline_period:
            coverage_query = text(f"""
                SELECT timestamp
                FROM {table_name}
                WHERE timestamp >= :query_start_ts AND symbol = :symbol AND exchange = :exchange {period_filter}
                ORDER BY timestamp
            """)
            expected_records = 1
        elif data_type == "klines" and period:
            coverage_query = text(f"""
                SELECT
                    to_char(to_timestamp(timestamp / {ts_divisor}) + interval :tz_interval, 'YYYY-MM-DD') as date,
                    COUNT(DISTINCT timestamp) as records
                FROM {table_name}
                WHERE timestamp >= :start_ts AND symbol = :symbol AND exchange = :exchange {period_filter}
                GROUP BY to_char(to_timestamp(timestamp / {ts_divisor}) + interval :tz_interval, 'YYYY-MM-DD')
                ORDER BY date
            """)
            expected_records = get_expected_kline_records_per_day(period)
        else:
            coverage_query = text(f"""
                SELECT
                    to_char(to_timestamp(timestamp / {ts_divisor}) + interval :tz_interval, 'YYYY-MM-DD') as date,
                    COUNT(DISTINCT to_char(to_timestamp(timestamp / {ts_divisor}) + interval :tz_interval, 'HH24')) as records
                FROM {table_name}
                WHERE timestamp >= :start_ts AND symbol = :symbol AND exchange = :exchange {period_filter}
                GROUP BY to_char(to_timestamp(timestamp / {ts_divisor}) + interval :tz_interval, 'YYYY-MM-DD')
                ORDER BY date
            """)
            expected_records = 24

        result = db.execute(coverage_query, params)
        rows = result.fetchall()

        # Build coverage list
        coverage_map = {}
        if is_span_kline_period:
            for row in rows:
                open_date = datetime.fromtimestamp(int(row[0]), tz=tz.utc).astimezone(local_tz).date()
                if period == "1M":
                    if open_date.month == 12:
                        next_month = open_date.replace(year=open_date.year + 1, month=1, day=1)
                    else:
                        next_month = open_date.replace(month=open_date.month + 1, day=1)
                    span_end = next_month - timedelta(days=1)
                else:
                    span_days = 7 if period == "1w" else 3
                    span_end = open_date + timedelta(days=span_days - 1)

                current_span_date = max(open_date, start_date)
                span_stop = min(span_end, end_date)
                while current_span_date <= span_stop:
                    coverage_map[current_span_date.strftime("%Y-%m-%d")] = 100
                    current_span_date += timedelta(days=1)
        else:
            for row in rows:
                date_str = row[0]
                records = row[1]
                coverage_pct = min(100, round(records / expected_records * 100))
                coverage_map[date_str] = coverage_pct

        # Generate date list
        coverage = []
        current = start_date
        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            coverage.append({
                "date": date_str,
                "pct": coverage_map.get(date_str, 0)
            })
            current += timedelta(days=1)

        pct_values = [item["pct"] for item in coverage]
        covered_days = sum(1 for pct in pct_values if pct > 0)
        missing_days = len(coverage) - covered_days
        coverage_mode = "hourly_presence"
        coverage_unit = "hour"
        if data_type == "klines":
            coverage_mode = "period_span" if is_span_kline_period else "daily_expected_records"
            coverage_unit = "span" if is_span_kline_period else "record"

        return {
            "symbol": symbol.upper(),
            "days": days,
            "coverage": coverage,
            "exchange": exchange,
            "data_type": data_type,
            "period": period,
            "summary": {
                "window_start": start_date.strftime("%Y-%m-%d"),
                "window_end": end_date.strftime("%Y-%m-%d"),
                "covered_days": covered_days,
                "missing_days": missing_days,
                "min_pct": min(pct_values) if pct_values else 0,
                "max_pct": max(pct_values) if pct_values else 0,
                "avg_pct": round(sum(pct_values) / len(pct_values), 2) if pct_values else 0,
                "expected_records_per_day": expected_records,
                "coverage_mode": coverage_mode,
                "coverage_unit": coverage_unit,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get data coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retention-days")
def get_retention_days_api(exchange: str = "hyperliquid", db: Session = Depends(get_db)):
    """Get current retention days setting for specific exchange"""
    days = get_retention_days(db, exchange)
    return RetentionDaysResponse(days=days, exchange=exchange)


@router.put("/retention-days")
def update_retention_days(request: RetentionDaysRequest, db: Session = Depends(get_db)):
    """Update retention days setting for specific exchange"""
    if request.days < 7 or request.days > 730:
        raise HTTPException(status_code=400, detail="Retention days must be between 7 and 730")

    days = set_retention_days(db, request.days, request.exchange)
    logger.info(f"Updated {request.exchange} retention to {days} days")

    return RetentionDaysResponse(days=days, exchange=request.exchange)


@router.get("/collection-days")
def get_collection_days(exchange: str = "hyperliquid", db: Session = Depends(get_db)):
    """Get total days of market flow data collection for specific exchange.
    Calculated from earliest record timestamp to now.
    """
    try:
        import time
        query = text("SELECT MIN(timestamp) FROM market_trades_aggregated WHERE exchange = :exchange")
        result = db.execute(query, {"exchange": exchange}).scalar()

        if not result:
            return {"days": 0, "exchange": exchange}

        now_ms = int(time.time() * 1000)
        days = (now_ms - result) / (24 * 60 * 60 * 1000)
        return {"days": round(days, 1), "exchange": exchange}
    except Exception as e:
        logger.error(f"Failed to get collection days: {e}")
        return {"days": 0, "exchange": exchange}


# ==================== Binance Backfill ====================

@router.post("/binance/backfill")
async def start_binance_backfill(
    force: bool = False,
    db: Session = Depends(get_db)
):
    """Start Binance historical data backfill task.
    Uses current Binance watchlist symbols.
    Backfills: K-lines for configured retention days, OI (real-time only),
    Funding (365d), Sentiment (30d).

    Args:
        force: If True, cancel any running/pending tasks and start fresh
    """
    from database.models import BinanceBackfillTask
    from services.binance_symbol_service import get_selected_symbols as get_binance_selected_symbols
    from services.exchanges.binance_backfill import binance_backfill_service
    import asyncio

    # Check if already running
    running_task = db.query(BinanceBackfillTask).filter(
        BinanceBackfillTask.status.in_(["pending", "running"])
    ).first()

    if running_task:
        if force:
            # Cancel all running/pending tasks
            db.query(BinanceBackfillTask).filter(
                BinanceBackfillTask.status.in_(["pending", "running"])
            ).update({"status": "cancelled"})
            db.commit()
        else:
            raise HTTPException(status_code=400, detail="A backfill task is already running")

    # Get Binance watchlist symbols
    symbols = get_binance_selected_symbols()
    if not symbols:
        symbols = ["BTC"]
    retention_days = get_retention_days(db, "binance")
    logger.info(f"[Binance] Starting backfill with symbols: {symbols}")

    # Create task
    task = BinanceBackfillTask(
        symbols=",".join(symbols),
        status="pending",
        progress=0
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Start backfill in background
    asyncio.create_task(binance_backfill_service.start_backfill(task.id))

    return {
        "task_id": task.id,
        "symbols": symbols,
        "retention_days": retention_days,
        "status": "started"
    }


@router.get("/binance/backfill/status")
def get_binance_backfill_status(db: Session = Depends(get_db)):
    """Get current Binance backfill task status."""
    from database.models import BinanceBackfillTask

    # Get most recent task
    task = db.query(BinanceBackfillTask).order_by(
        BinanceBackfillTask.created_at.desc()
    ).first()

    if not task:
        return {"status": "none", "progress": 0}

    return {
        "task_id": task.id,
        "symbols": task.symbols.split(",") if task.symbols else [],
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None
    }


# ==================== Hyperliquid Backfill ====================

@router.post("/hyperliquid/backfill")
async def start_hyperliquid_backfill(db: Session = Depends(get_db)):
    """Start Hyperliquid K-line backfill task.
    Uses current watchlist symbols.
    Backfills: K-lines (~5000 records, ~3.5 days per symbol).
    """
    from database.models import HyperliquidBackfillTask
    from services.hyperliquid_symbol_service import get_selected_symbols
    from services.exchanges.hyperliquid_backfill import hyperliquid_backfill_service
    import asyncio

    # Check if already running
    running_task = db.query(HyperliquidBackfillTask).filter(
        HyperliquidBackfillTask.status.in_(["pending", "running"])
    ).first()
    if running_task:
        raise HTTPException(status_code=400, detail="A backfill task is already running")

    # Get watchlist symbols
    symbols = get_selected_symbols()
    if not symbols:
        symbols = ["BTC"]

    # Create task
    task = HyperliquidBackfillTask(
        symbols=",".join(symbols),
        status="pending",
        progress=0
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Start backfill in background
    asyncio.create_task(hyperliquid_backfill_service.start_backfill(task.id))

    return {
        "task_id": task.id,
        "symbols": symbols,
        "status": "started"
    }


@router.get("/hyperliquid/backfill/status")
def get_hyperliquid_backfill_status(db: Session = Depends(get_db)):
    """Get current Hyperliquid backfill task status."""
    from database.models import HyperliquidBackfillTask

    # Get most recent task
    task = db.query(HyperliquidBackfillTask).order_by(
        HyperliquidBackfillTask.created_at.desc()
    ).first()

    if not task:
        return {"status": "none", "progress": 0}

    return {
        "task_id": task.id,
        "symbols": task.symbols.split(",") if task.symbols else [],
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None
    }
