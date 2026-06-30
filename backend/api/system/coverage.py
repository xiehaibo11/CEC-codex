"""Data coverage system route."""

import logging
import time
from datetime import datetime, timedelta, timezone as tz
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import get_db
from services.exchanges.binance_constants import (
    BINANCE_KLINE_INTERVAL_SECONDS,
    BINANCE_KLINE_INTERVALS,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_expected_kline_records_per_day(period: str) -> int:
    """Return the expected number of K-line records per calendar day."""
    interval_seconds = BINANCE_KLINE_INTERVAL_SECONDS.get(period)
    if not interval_seconds:
        return 24
    if interval_seconds >= 24 * 60 * 60:
        return 1
    return max(1, (24 * 60 * 60) // interval_seconds)


@router.get("/data-coverage")
def get_data_coverage(
    days: int = 30,
    symbol: Optional[str] = None,
    tz_offset: int = 0,
    exchange: str = "hyperliquid",
    data_type: str = "market_flow",
    period: Optional[str] = None,
    db: Session = Depends(get_db),
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
                "pct": coverage_map.get(date_str, 0),
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
