"""Cached Hyperliquid market-data client helpers."""

from typing import Any, Dict, List, Optional

from services.hyperliquid_market_data import HyperliquidClient

_client_cache: dict[str, HyperliquidClient] = {}


def create_hyperliquid_client(environment: str = "mainnet") -> HyperliquidClient:
    """Create a new HyperliquidClient instance for the specified environment."""
    return HyperliquidClient(environment=environment)


def get_hyperliquid_client_for_environment(environment: str = "mainnet") -> HyperliquidClient:
    """Get cached HyperliquidClient instance for the specified environment."""
    if environment not in _client_cache:
        _client_cache[environment] = create_hyperliquid_client(environment)
    return _client_cache[environment]


def get_default_hyperliquid_client() -> HyperliquidClient:
    """Get default HyperliquidClient (mainnet) for backward compatibility."""
    return get_hyperliquid_client_for_environment("mainnet")


def get_last_price_from_hyperliquid(symbol: str, environment: str = "mainnet") -> Optional[float]:
    """Get last price from Hyperliquid."""
    client = get_hyperliquid_client_for_environment(environment)
    return client.get_last_price(symbol)


def get_kline_data_from_hyperliquid(
    symbol: str,
    period: str = '1d',
    count: int = 100,
    persist: bool = True,
    environment: str = "mainnet",
) -> List[Dict[str, Any]]:
    """Get kline data from Hyperliquid."""
    client = get_hyperliquid_client_for_environment(environment)
    return client.get_kline_data(symbol, period, count, persist)


def get_historical_kline_data_from_hyperliquid(
    symbol: str,
    period: str,
    since_ms: int,
    until_ms: int = None,
    environment: str = "mainnet",
) -> List[Dict[str, Any]]:
    """Get historical kline data from Hyperliquid for a specific time range."""
    client = get_hyperliquid_client_for_environment(environment)
    return client.get_historical_kline_data(symbol, period, since_ms, until_ms)


def get_market_status_from_hyperliquid(
    symbol: str,
    environment: str = "mainnet",
) -> Dict[str, Any]:
    """Get market status from Hyperliquid."""
    client = get_hyperliquid_client_for_environment(environment)
    return client.get_market_status(symbol)


def get_all_symbols_from_hyperliquid(environment: str = "mainnet") -> List[str]:
    """Get all available symbols from Hyperliquid."""
    client = get_hyperliquid_client_for_environment(environment)
    return client.get_all_symbols()


def get_ticker_data_from_hyperliquid(
    symbol: str,
    environment: str = "mainnet",
) -> Optional[Dict[str, Any]]:
    """Get complete ticker data from Hyperliquid."""
    client = get_hyperliquid_client_for_environment(environment)
    return client.get_ticker_data(symbol)
