"""Storage statistics system route."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import get_db

from .retention import get_retention_days

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/storage-stats")
def get_storage_stats(exchange: str = "hyperliquid", db: Session = Depends(get_db)):
    """Get storage statistics for market flow data tables by exchange"""
    try:
        # Tables with exchange column
        tables_with_exchange = [
            "market_trades_aggregated",
            "market_asset_metrics",
            "market_orderbook_snapshots",
            "crypto_klines",
        ]
        if exchange == "binance":
            tables_with_exchange.append("market_sentiment_metrics")

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
            "estimated_per_symbol_per_day_mb": round(per_symbol_per_day, 2),
        }
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
