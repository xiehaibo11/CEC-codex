"""
Market Flow summary endpoints.

Product-oriented flow summary cards and large-order zone buckets used by the
frontend insight timeline. These reuse aggregated DB tables and do not depend
on SSE or signal-generation logic.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import MarketTradesAggregated, MarketAssetMetrics

from ._base import (
    router,
    get_db,
    TIMEFRAME_MS,
    decimal_to_float,
    MarketFlowSummaryResponse,
    LargeOrderZoneResponse,
)


@router.get("/summary", response_model=MarketFlowSummaryResponse)
def get_market_flow_summary(
    symbols: str = Query(..., description="Comma-separated symbols, e.g. BTC,ETH"),
    exchange: str = Query("hyperliquid", description="Exchange: hyperliquid or binance"),
    window: str = Query("1h", description="Summary window"),
    end_time: Optional[int] = Query(None, description="End timestamp in ms"),
    db: Session = Depends(get_db)
):
    """
    Get lightweight market flow summary cards for frontend display.

    This endpoint is intentionally product-oriented:
    - focuses on human-readable flow summary values
    - reuses aggregated DB tables
    - does not depend on SSE or signal-generation logic
    """
    if window not in TIMEFRAME_MS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid window. Supported: {list(TIMEFRAME_MS.keys())}"
        )

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")
    if len(symbol_list) > 20:
        raise HTTPException(status_code=400, detail="Too many symbols requested")

    exchange = exchange.lower()
    if exchange not in {"hyperliquid", "binance"}:
        raise HTTPException(status_code=400, detail="Invalid exchange")

    if end_time is None:
        end_time = int(datetime.utcnow().timestamp() * 1000)
    start_time = end_time - TIMEFRAME_MS[window]

    items = [
        _build_market_flow_summary_item(
            db=db,
            symbol=symbol,
            exchange=exchange,
            window=window,
            start_time=start_time,
            end_time=end_time,
        )
        for symbol in symbol_list
    ]

    return {
        "exchange": exchange,
        "window": window,
        "items": items,
    }


@router.get("/large-order-zones", response_model=LargeOrderZoneResponse)
def get_large_order_zones(
    symbol: str = Query(..., description="Trading symbol, e.g. BTC"),
    exchange: str = Query("hyperliquid", description="Exchange: hyperliquid or binance"),
    timeframe: str = Query("15m", description="Aggregation timeframe"),
    start_time: Optional[int] = Query(None, description="Start timestamp in ms"),
    end_time: Optional[int] = Query(None, description="End timestamp in ms"),
    db: Session = Depends(get_db)
):
    """
    Get large-order flow buckets for event markers on the insight timeline.
    This is a lightweight product API rather than a full signal endpoint.
    """
    if timeframe not in TIMEFRAME_MS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Supported: {list(TIMEFRAME_MS.keys())}"
        )

    exchange = exchange.lower()
    if exchange not in {"hyperliquid", "binance"}:
        raise HTTPException(status_code=400, detail="Invalid exchange")

    interval_ms = TIMEFRAME_MS[timeframe]
    if end_time is None:
        end_time = int(datetime.utcnow().timestamp() * 1000)
    if start_time is None:
        start_time = end_time - (7 * 24 * 60 * 60 * 1000)

    bucket_expr = func.floor(MarketTradesAggregated.timestamp / interval_ms) * interval_ms

    rows = db.query(
        bucket_expr.label("bucket_time"),
        func.sum(MarketTradesAggregated.large_buy_notional).label("large_buy_notional"),
        func.sum(MarketTradesAggregated.large_sell_notional).label("large_sell_notional"),
        func.sum(MarketTradesAggregated.large_buy_count).label("large_buy_count"),
        func.sum(MarketTradesAggregated.large_sell_count).label("large_sell_count"),
    ).filter(
        MarketTradesAggregated.symbol == symbol.upper(),
        MarketTradesAggregated.exchange == exchange,
        MarketTradesAggregated.timestamp >= start_time,
        MarketTradesAggregated.timestamp <= end_time,
    ).group_by(
        bucket_expr,
    ).order_by(
        bucket_expr.asc()
    ).all()

    items = []
    for row in rows:
        large_buy_notional = decimal_to_float(row.large_buy_notional) or 0
        large_sell_notional = decimal_to_float(row.large_sell_notional) or 0
        items.append({
            "time": int(row.bucket_time),
            "large_buy_notional": large_buy_notional,
            "large_sell_notional": large_sell_notional,
            "large_order_net": large_buy_notional - large_sell_notional,
            "large_buy_count": int(row.large_buy_count or 0),
            "large_sell_count": int(row.large_sell_count or 0),
        })

    return {
        "symbol": symbol.upper(),
        "exchange": exchange,
        "timeframe": timeframe,
        "items": items,
    }


def _build_market_flow_summary_item(
    db: Session,
    symbol: str,
    exchange: str,
    window: str,
    start_time: int,
    end_time: int,
) -> Dict[str, Any]:
    trade_row = db.query(
        func.max(MarketTradesAggregated.timestamp),
        func.sum(MarketTradesAggregated.taker_buy_notional),
        func.sum(MarketTradesAggregated.taker_sell_notional),
        func.sum(MarketTradesAggregated.large_buy_notional),
        func.sum(MarketTradesAggregated.large_sell_notional),
        func.sum(MarketTradesAggregated.large_buy_count),
        func.sum(MarketTradesAggregated.large_sell_count),
    ).filter(
        MarketTradesAggregated.symbol == symbol,
        MarketTradesAggregated.exchange == exchange,
        MarketTradesAggregated.timestamp >= start_time,
        MarketTradesAggregated.timestamp <= end_time,
    ).one()

    latest_trade_ts, buy_sum, sell_sum, large_buy_sum, large_sell_sum, large_buy_count, large_sell_count = trade_row

    total_buy = decimal_to_float(buy_sum) or 0.0
    total_sell = decimal_to_float(sell_sum) or 0.0
    large_buy = decimal_to_float(large_buy_sum) or 0.0
    large_sell = decimal_to_float(large_sell_sum) or 0.0
    total_flow = total_buy + total_sell
    net_inflow = total_buy - total_sell
    large_order_net = large_buy - large_sell
    retail_net = net_inflow - large_order_net
    buy_ratio = (total_buy / total_flow) if total_flow > 0 else 0.0

    oi_records = db.query(
        MarketAssetMetrics.timestamp,
        MarketAssetMetrics.open_interest,
    ).filter(
        MarketAssetMetrics.symbol == symbol,
        MarketAssetMetrics.exchange == exchange,
        MarketAssetMetrics.timestamp >= start_time,
        MarketAssetMetrics.timestamp <= end_time,
        MarketAssetMetrics.open_interest.isnot(None),
    ).order_by(MarketAssetMetrics.timestamp.asc()).all()

    open_interest_change_pct = None
    if len(oi_records) >= 2:
        first_oi = decimal_to_float(oi_records[0][1])
        last_oi = decimal_to_float(oi_records[-1][1])
        if first_oi not in (None, 0) and last_oi is not None:
            open_interest_change_pct = ((last_oi - first_oi) / first_oi) * 100

    funding_row = db.query(
        MarketAssetMetrics.funding_rate
    ).filter(
        MarketAssetMetrics.symbol == symbol,
        MarketAssetMetrics.exchange == exchange,
        MarketAssetMetrics.timestamp >= start_time,
        MarketAssetMetrics.timestamp <= end_time,
        MarketAssetMetrics.funding_rate.isnot(None),
    ).order_by(MarketAssetMetrics.timestamp.desc()).first()

    funding_rate_pct = None
    if funding_row and funding_row[0] is not None:
        funding_rate_pct = float(funding_row[0]) * 100

    return {
        "symbol": symbol,
        "exchange": exchange,
        "window": window,
        "start_time": start_time,
        "end_time": end_time,
        "latest_trade_timestamp": latest_trade_ts,
        "total_buy_notional": total_buy,
        "total_sell_notional": total_sell,
        "net_inflow": net_inflow,
        "buy_ratio": buy_ratio,
        "total_large_buy_notional": large_buy,
        "total_large_sell_notional": large_sell,
        "large_order_net": large_order_net,
        "retail_net": retail_net,
        "large_buy_count": int(large_buy_count or 0),
        "large_sell_count": int(large_sell_count or 0),
        "open_interest_change_pct": open_interest_change_pct,
        "funding_rate_pct": funding_rate_pct,
    }
