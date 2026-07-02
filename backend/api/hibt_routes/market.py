"""HiBT public market-data and symbol-watchlist endpoints."""
from __future__ import annotations

from typing import List

from fastapi import HTTPException
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
    """Update HiBT watchlist (max 10 symbols)."""
    from services.hibt_symbol_service import MAX_WATCHLIST_SYMBOLS, update_selected_symbols

    try:
        symbols = update_selected_symbols(payload.symbols)
        return {
            "symbols": symbols,
            "max_symbols": MAX_WATCHLIST_SYMBOLS,
        }
    except Exception as err:
        logger.error("[HiBT] Failed to update watchlist: %s", err, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update HiBT watchlist")
