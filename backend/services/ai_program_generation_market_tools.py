"""Market data tools for AI program generation."""
import json
from typing import Optional

from sqlalchemy.orm import Session

def _query_market_data(db: Session, symbol: str, period: str, exchange: str = "hyperliquid") -> str:
    """Query current market data for AI to understand indicator value ranges.

    Args:
        db: Database session
        symbol: Trading symbol (e.g., BTC, ETH)
        period: Time period for indicators (e.g., 1h, 5m)
        exchange: Exchange to query from ('hyperliquid' or 'binance')
    """
    try:
        from program_trader.data_provider import DataProvider
        import requests

        # Get current price based on exchange
        if exchange == "binance":
            # Use Binance public API to get price
            binance_symbol = f"{symbol.upper()}USDT"
            resp = requests.get(
                "https://fapi.binance.com/fapi/v1/ticker/price",
                params={"symbol": binance_symbol},
                timeout=5
            )
            if resp.status_code == 200:
                price = float(resp.json().get("price", 0))
            else:
                price = None
        else:
            from services.hyperliquid_market_data import get_last_price_from_hyperliquid
            price = get_last_price_from_hyperliquid(symbol, "mainnet")

        # Create data provider with exchange parameter
        data_provider = DataProvider(db=db, account_id=0, environment="mainnet", exchange=exchange)

        # Get all indicators
        indicators = {}
        for ind in ["RSI14", "RSI7", "MA5", "MA10", "MA20", "EMA20", "EMA50", "EMA100",
                    "MACD", "BOLL", "ATR14", "VWAP", "STOCH", "OBV"]:
            result = data_provider.get_indicator(symbol, ind, period)
            if result:
                indicators[ind] = result

        # Get all flow metrics
        flow_metrics = {}
        for metric in ["CVD", "OI", "OI_DELTA", "TAKER", "FUNDING", "DEPTH", "IMBALANCE"]:
            result = data_provider.get_flow(symbol, metric, period)
            if result:
                flow_metrics[metric] = result

        # Get regime
        regime = data_provider.get_regime(symbol, period)

        # Format response
        result = {
            "symbol": symbol,
            "period": period,
            "exchange": exchange,
            "current_price": float(price) if price else None,
            "indicators": indicators,
            "flow_metrics": flow_metrics,
            "regime": {"regime": regime.regime, "confidence": regime.conf}
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})
