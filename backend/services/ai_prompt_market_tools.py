"""Market-data tool for AI Prompt generation."""

import json
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def execute_query_market_data(
    db: Session,
    symbol: str,
    period: str = "1h",
    exchange: str = "hyperliquid",
) -> str:
    """Query current market data for AI to understand indicator value ranges."""
    try:
        import requests
        from program_trader.data_provider import DataProvider

        price = None
        if exchange == "binance":
            binance_symbol = f"{symbol.upper()}USDT"
            try:
                resp = requests.get(
                    "https://fapi.binance.com/fapi/v1/ticker/price",
                    params={"symbol": binance_symbol},
                    timeout=5,
                )
                if resp.status_code == 200:
                    price = float(resp.json().get("price", 0))
            except Exception as exc:
                logger.warning(f"[query_market_data] Failed to get Binance price: {exc}")
        else:
            from services.hyperliquid_market_data import get_last_price_from_hyperliquid
            price = get_last_price_from_hyperliquid(symbol, "mainnet")

        data_provider = DataProvider(db=db, account_id=0, environment="mainnet", exchange=exchange)

        indicators = {}
        for indicator in [
            "RSI14",
            "RSI7",
            "MA5",
            "MA10",
            "MA20",
            "EMA20",
            "EMA50",
            "EMA100",
            "MACD",
            "BOLL",
            "ATR14",
            "VWAP",
            "STOCH",
            "OBV",
        ]:
            value = data_provider.get_indicator(symbol, indicator, period)
            if value:
                indicators[indicator] = value

        flow_metrics = {}
        for metric in ["CVD", "OI", "OI_DELTA", "TAKER", "FUNDING", "DEPTH", "IMBALANCE"]:
            value = data_provider.get_flow(symbol, metric, period)
            if value:
                flow_metrics[metric] = value

        regime = data_provider.get_regime(symbol, period)
        result = {
            "symbol": symbol,
            "period": period,
            "exchange": exchange,
            "current_price": float(price) if price else None,
            "indicators": indicators,
            "flow_metrics": flow_metrics,
            "regime": {"regime": regime.regime, "confidence": regime.conf} if regime else None,
        }

        return json.dumps(result, indent=2)

    except Exception as exc:
        logger.error(f"[query_market_data] Error: {exc}")
        return json.dumps({"error": str(exc)})
