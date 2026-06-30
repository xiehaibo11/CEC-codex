"""
Binance public market-data and symbol-watchlist endpoints.

Public price lookups plus the tradable-symbol watchlist (list/get/update),
which also refreshes the running Binance data collectors.
"""
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List

from ._shared import router, logger


@router.get("/price/{symbol}")
def get_price(symbol: str):
    """
    Get current price for a symbol from Binance Futures.
    This is a public endpoint that doesn't require authentication.
    """
    import requests
    try:
        binance_symbol = symbol.upper()
        if not binance_symbol.endswith("USDT"):
            binance_symbol = f"{binance_symbol}USDT"

        # Use public API endpoint (no auth required)
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={binance_symbol}"
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to get price")

        data = response.json()
        return {
            "symbol": symbol.upper(),
            "price": float(data.get("price", 0)),
            "binance_symbol": binance_symbol
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get Binance price: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Symbol Watchlist API ====================

class BinanceSymbolSelectionRequest(BaseModel):
    """Request model for updating Binance watchlist"""
    symbols: List[str] = Field(default_factory=list, description="Symbols to monitor")

    class Config:
        json_schema_extra = {
            "example": {
                "symbols": ["BTC", "ETH", "SOL"]
            }
        }


@router.get("/symbols/available")
def list_available_symbols():
    """Return cached Binance tradable symbols (refreshed periodically)."""
    from services.binance_symbol_service import get_available_symbols_info, MAX_WATCHLIST_SYMBOLS
    info = get_available_symbols_info()
    return {
        "symbols": info.get("symbols", []),
        "count": info.get("count", 0),
        "max_symbols": MAX_WATCHLIST_SYMBOLS,
    }


@router.get("/symbols/watchlist")
def get_symbol_watchlist():
    """Return the currently configured Binance watchlist."""
    from services.binance_symbol_service import get_selected_symbols, MAX_WATCHLIST_SYMBOLS
    symbols = get_selected_symbols()
    return {
        "symbols": symbols,
        "max_symbols": MAX_WATCHLIST_SYMBOLS,
    }


@router.put("/symbols/watchlist")
def update_symbol_watchlist(payload: BinanceSymbolSelectionRequest):
    """Update Binance watchlist (max 10 symbols).
    Also updates Binance data collectors to use the new symbols.
    """
    from services.binance_symbol_service import update_selected_symbols, MAX_WATCHLIST_SYMBOLS

    try:
        symbols = update_selected_symbols(payload.symbols)

        # Update Binance collectors with new symbols
        try:
            from services.exchanges.binance_collector import binance_collector
            if binance_collector.running:
                binance_collector.refresh_symbols(symbols if symbols else ["BTC"])
                logger.info(f"[Binance] Collector symbols updated to: {symbols}")
        except Exception as e:
            logger.warning(f"[Binance] Failed to update collector symbols: {e}")

        try:
            from services.exchanges.binance_ws_collector import binance_ws_collector
            if binance_ws_collector.running:
                binance_ws_collector.refresh_symbols(symbols if symbols else ["BTC"])
                logger.info(f"[Binance] WS collector symbols updated to: {symbols}")
        except Exception as e:
            logger.warning(f"[Binance] Failed to update WS collector symbols: {e}")

        return {
            "symbols": symbols,
            "max_symbols": MAX_WATCHLIST_SYMBOLS,
        }
    except Exception as err:
        logger.error(f"[Binance] Failed to update watchlist: {err}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update Binance watchlist")
