"""Metric analysis and signal/pool backtest endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from ._base import MARKET_SIGNAL_SOURCE, get_db, logger, router


# ============ Metric Analysis ============

@router.get("/analyze")
def analyze_metric(
    symbol: str = Query(..., description="Trading symbol (e.g., BTC)"),
    metric: str = Query(..., description="Metric type (e.g., oi_delta_percent)"),
    period: str = Query("5m", description="Time period (e.g., 5m, 15m)"),
    days: int = Query(7, le=30, description="Days of history to analyze"),
    exchange: str = Query("hyperliquid", description="Exchange (hyperliquid or binance)"),
    db: Session = Depends(get_db)
):
    """
    Analyze a metric and provide statistical summary with threshold suggestions.

    Returns statistics and suggested thresholds based on historical data.
    """
    from services.signal_analysis_service import signal_analysis_service

    result = signal_analysis_service.analyze_metric(db, symbol, metric, period, days, exchange)
    return result


# ============ Signal Backtest Preview ============

@router.get("/backtest/{signal_id}")
def backtest_signal(
    signal_id: int,
    symbol: str = Query(..., description="Trading symbol (e.g., BTC)"),
    kline_min_ts: int = Query(None, description="Min K-line timestamp in ms (for filtering triggers)"),
    kline_max_ts: int = Query(None, description="Max K-line timestamp in ms (for filtering triggers)"),
    db: Session = Depends(get_db)
):
    """
    Backtest a signal against historical data.
    Returns only trigger points - K-lines should be fetched via /api/market/kline-with-indicators.
    """
    from services.signal_backtest_service import signal_backtest_service

    try:
        result = signal_backtest_service.backtest_signal(db, signal_id, symbol, kline_min_ts, kline_max_ts)
        return result
    except Exception as e:
        logger.error(
            f"[Backtest API] EXCEPTION: signal_id={signal_id}, symbol={symbol}, "
            f"ts_range=[{kline_min_ts}, {kline_max_ts}], error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


class TempBacktestRequest(BaseModel):
    """Request for temporary signal backtest (without saving to database)"""
    symbol: str = Field(..., description="Trading symbol (e.g., BTC)")
    trigger_condition: dict = Field(..., alias="triggerCondition", description="Signal trigger condition")
    kline_min_ts: Optional[int] = Field(None, alias="klineMinTs", description="Min K-line timestamp in ms")
    kline_max_ts: Optional[int] = Field(None, alias="klineMaxTs", description="Max K-line timestamp in ms")
    exchange: str = Field("hyperliquid", description="Exchange (hyperliquid or binance)")

    class Config:
        populate_by_name = True


@router.post("/backtest-preview")
def backtest_preview(
    request: TempBacktestRequest,
    db: Session = Depends(get_db)
):
    """
    Backtest a signal configuration without saving to database.
    Used for AI signal creation preview before actually creating the signal.
    """
    from services.signal_backtest_service import signal_backtest_service

    try:
        result = signal_backtest_service.backtest_temp_signal(
            db=db,
            symbol=request.symbol,
            trigger_condition=request.trigger_condition,
            kline_min_ts=request.kline_min_ts,
            kline_max_ts=request.kline_max_ts,
            exchange=request.exchange
        )
        return result
    except Exception as e:
        logger.error(
            f"[Backtest API] EXCEPTION in preview: symbol={request.symbol}, "
            f"condition={request.trigger_condition}, error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Backtest preview failed: {str(e)}")


@router.get("/pool-backtest/{pool_id}")
def backtest_pool(
    pool_id: int,
    symbol: str = Query(..., description="Trading symbol (e.g., BTC)"),
    kline_min_ts: int = Query(None, description="Min K-line timestamp in ms"),
    kline_max_ts: int = Query(None, description="Max K-line timestamp in ms"),
    db: Session = Depends(get_db)
):
    """
    Backtest a signal pool against historical data.
    Combines triggers from multiple signals based on pool logic (AND/OR).
    """
    from services.signal_backtest_service import signal_backtest_service

    try:
        pool_meta = db.execute(text("""
            SELECT source_type FROM signal_pools
            WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
        """), {"id": pool_id}).fetchone()
        if not pool_meta:
            raise HTTPException(status_code=404, detail="Pool not found")
        if (pool_meta[0] or MARKET_SIGNAL_SOURCE) != MARKET_SIGNAL_SOURCE:
            raise HTTPException(status_code=400, detail="Wallet tracking pools do not support backtest")
        result = signal_backtest_service.backtest_pool(db, pool_id, symbol, kline_min_ts, kline_max_ts)
        return result
    except Exception as e:
        logger.error(
            f"[Backtest API] EXCEPTION in pool: pool_id={pool_id}, symbol={symbol}, "
            f"ts_range=[{kline_min_ts}, {kline_max_ts}], error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Pool backtest failed: {str(e)}")
