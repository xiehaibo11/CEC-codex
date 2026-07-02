"""Hyper AI market data query handlers."""

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def execute_get_klines(
    db: Session,
    symbol: str,
    period: str = "1h",
    limit: int = 50,
    exchange: str = "hyperliquid",
) -> str:
    """Get K-line data for a symbol."""
    from database.models import CryptoKline

    try:
        limit = min(max(limit, 1), 200)

        klines = db.query(CryptoKline).filter(
            CryptoKline.exchange == exchange,
            CryptoKline.symbol == symbol.upper(),
            CryptoKline.period == period,
            CryptoKline.environment == "mainnet",
        ).order_by(CryptoKline.timestamp.desc()).limit(limit).all()

        candles = []
        for kline in reversed(klines):
            candles.append({
                "time": datetime.utcfromtimestamp(kline.timestamp).strftime("%Y-%m-%d %H:%M UTC"),
                "open": float(kline.open_price) if kline.open_price else 0,
                "high": float(kline.high_price) if kline.high_price else 0,
                "low": float(kline.low_price) if kline.low_price else 0,
                "close": float(kline.close_price) if kline.close_price else 0,
                "volume": float(kline.volume) if kline.volume else 0,
            })

        return json.dumps({
            "symbol": symbol.upper(),
            "period": period,
            "exchange": exchange,
            "candles": candles,
            "count": len(candles),
        }, indent=2)

    except Exception as exc:
        logger.error(f"[get_klines] Error: {exc}")
        return json.dumps({"error": str(exc)})


def execute_get_market_regime(
    db: Session,
    symbol: str,
    period: str = "1h",
    exchange: str = "hyperliquid",
) -> str:
    """Get market regime classification for a symbol."""
    try:
        from program_trader.data_provider import DataProvider

        data_provider = DataProvider(db=db, account_id=0, environment="mainnet", exchange=exchange)
        regime = data_provider.get_regime(symbol.upper(), period)

        if regime:
            return json.dumps({
                "symbol": symbol.upper(),
                "period": period,
                "exchange": exchange,
                "regime": regime.regime,
                "confidence": regime.conf,
            }, indent=2)

        return json.dumps({
            "symbol": symbol.upper(),
            "period": period,
            "exchange": exchange,
            "regime": "unknown",
            "confidence": 0,
            "note": "Unable to determine market regime",
        })

    except Exception as exc:
        logger.error(f"[get_market_regime] Error: {exc}")
        return json.dumps({"error": str(exc)})


def execute_get_market_flow(
    db: Session,
    symbol: str,
    period: str = "1h",
    exchange: str = "hyperliquid",
) -> str:
    """Get market flow data for a symbol."""
    try:
        from program_trader.data_provider import DataProvider

        data_provider = DataProvider(db=db, account_id=0, environment="mainnet", exchange=exchange)
        flow = {}
        for metric in ["CVD", "OI", "OI_DELTA", "TAKER", "FUNDING"]:
            result = data_provider.get_flow(symbol.upper(), metric, period)
            if result:
                flow[metric] = result

        return json.dumps({
            "symbol": symbol.upper(),
            "period": period,
            "exchange": exchange,
            "flow": flow,
        }, indent=2)

    except Exception as exc:
        logger.error(f"[get_market_flow] Error: {exc}")
        return json.dumps({"error": str(exc)})
