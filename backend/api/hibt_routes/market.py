"""HiBT public market-data and symbol-watchlist endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

from services.hibt_trading_client import HibtTradingClient

from ._shared import logger, router


class HibtSymbolSelectionRequest(BaseModel):
    """Request model for updating HiBT watchlist."""

    symbols: List[str] = Field(default_factory=list, description="Symbols to monitor")

    class Config:
        json_schema_extra = {"example": {"symbols": ["BTC", "ETH", "SOL"]}}


@router.get("/price/{symbol}")
def get_price(symbol: str):
    """Get current price for a symbol from HiBT perpetual futures."""
    try:
        client = HibtTradingClient(access_key="", secret_key="")
        price = client.get_price(symbol)
        return {
            "symbol": symbol.upper(),
            "price": price,
            "hibt_symbol": HibtTradingClient.to_hibt_symbol(symbol),
        }
    except Exception as e:
        logger.error("Failed to get HiBT price: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/klines/{symbol}")
def get_klines(
    symbol: str,
    period: str = "1m",
    count: int = Query(200, ge=1, le=500),
    start: Optional[int] = None,
    end: Optional[int] = None,
):
    """Get HiBT candlestick data for a symbol."""
    try:
        client = HibtTradingClient(access_key="", secret_key="")
        klines = client.get_klines(symbol, period=period, start=start, end=end, count=count)
        return {"symbol": symbol.upper(), "period": period, "klines": klines}
    except Exception as e:
        logger.error("Failed to get HiBT klines: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/depth/{symbol}")
def get_depth(symbol: str, limit: int = 20):
    """Get HiBT order-book depth (limit: 5/10/20/50/100/200)."""
    if limit not in HibtTradingClient.DEPTH_LIMITS:
        raise HTTPException(status_code=400, detail=f"limit must be one of {HibtTradingClient.DEPTH_LIMITS}")
    try:
        client = HibtTradingClient(access_key="", secret_key="")
        return {"symbol": symbol.upper(), "depth": client.get_depth(symbol, limit=limit)}
    except Exception as e:
        logger.error("Failed to get HiBT depth: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deals/{symbol}")
def get_deals(symbol: str):
    """Get latest public HiBT trades for a symbol."""
    try:
        client = HibtTradingClient(access_key="", secret_key="")
        return {"symbol": symbol.upper(), "deals": client.get_deals(symbol)}
    except Exception as e:
        logger.error("Failed to get HiBT deals: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding-rate/{symbol}")
def get_funding_rate(
    symbol: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: Optional[int] = Query(None, le=1000),
):
    """Get HiBT funding-rate history (ms timestamps, 3-month max range)."""
    try:
        client = HibtTradingClient(access_key="", secret_key="")
        rates = client.get_funding_rate(symbol, start_time=start_time, end_time=end_time, limit=limit)
        return {"symbol": symbol.upper(), "rates": rates}
    except Exception as e:
        logger.error("Failed to get HiBT funding rate: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mark-price/{symbol}")
def get_mark_price(symbol: str):
    """Get HiBT mark/index price for a symbol."""
    try:
        client = HibtTradingClient(access_key="", secret_key="")
        prices = client.get_mark_prices(symbol)
        price = client._float(prices[0].get("marketPrice")) if prices and isinstance(prices[0], dict) else 0.0
        return {"symbol": symbol.upper(), "mark_price": price, "raw": prices}
    except Exception as e:
        logger.error("Failed to get HiBT mark price: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols/available")
def list_available_symbols():
    """Return cached HiBT tradable symbols."""
    from services.hibt_symbol_service import MAX_WATCHLIST_SYMBOLS, get_available_symbols_info

    info = get_available_symbols_info()
    return {
        "symbols": info.get("symbols", []),
        "count": info.get("count", 0),
        "max_symbols": MAX_WATCHLIST_SYMBOLS,
    }


@router.get("/symbols/watchlist")
def get_symbol_watchlist():
    """Return the currently configured HiBT watchlist."""
    from services.hibt_symbol_service import MAX_WATCHLIST_SYMBOLS, get_selected_symbols

    return {
        "symbols": get_selected_symbols(),
        "max_symbols": MAX_WATCHLIST_SYMBOLS,
    }


@router.put("/symbols/watchlist")
def update_symbol_watchlist(payload: HibtSymbolSelectionRequest):
    """Update HiBT watchlist (max 10 symbols) and running collectors."""
    from services.hibt_symbol_service import MAX_WATCHLIST_SYMBOLS, update_selected_symbols

    try:
        symbols = update_selected_symbols(payload.symbols)
        try:
            from services.exchanges.hibt_collector import hibt_collector

            if hibt_collector.running:
                hibt_collector.refresh_symbols(symbols if symbols else ["BTC"])
                logger.info("[HiBT] Collector symbols updated to: %s", symbols)
        except Exception as err:
            logger.warning("[HiBT] Failed to update collector symbols: %s", err)
        return {
            "symbols": symbols,
            "max_symbols": MAX_WATCHLIST_SYMBOLS,
        }
    except Exception as err:
        logger.error("[HiBT] Failed to update watchlist: %s", err, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update HiBT watchlist")
