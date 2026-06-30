from __future__ import annotations

import time
from typing import Any

from .catalog import INTERVAL_MINUTES, _normalize_plan

EVENT_CONTRACT_REQUIRED_METRICS: list[dict[str, Any]] = [
    {
        "metric": "aggregated_cvd",
        "label": "Aggregated CVD",
        "path": "/api/futures/aggregated-cvd/history",
        "params": lambda coin, pair, exchange, interval: {
            "exchange_list": exchange,
            "symbol": coin,
            "interval": interval,
            "limit": 1,
        },
    },
    {
        "metric": "pair_taker_volume",
        "label": "Pair taker buy/sell",
        "path": "/api/futures/v2/taker-buy-sell-volume/history",
        "params": lambda coin, pair, exchange, interval: {
            "exchange": exchange,
            "symbol": pair,
            "interval": interval,
            "limit": 1,
        },
    },
    {
        "metric": "open_interest",
        "label": "Aggregated open interest",
        "path": "/api/futures/open-interest/aggregated-history",
        "params": lambda coin, pair, exchange, interval: {
            "symbol": coin,
            "interval": interval,
            "limit": 1,
            "unit": "usd",
        },
    },
    {
        "metric": "funding_rate",
        "label": "Funding rate",
        "path": "/api/futures/funding-rate/history",
        "params": lambda coin, pair, exchange, interval: {
            "exchange": exchange,
            "symbol": pair,
            "interval": interval,
            "limit": 1,
        },
    },
    {
        "metric": "pair_liquidation",
        "label": "Pair liquidation",
        "path": "/api/futures/liquidation/history",
        "params": lambda coin, pair, exchange, interval: {
            "exchange": exchange,
            "symbol": pair,
            "interval": interval,
            "limit": 1,
        },
    },
]

CAPABILITY_CACHE_TTL_SECONDS = 10 * 60
_event_contract_capability_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _coinglass_exchange_name(exchange: str | None) -> str:
    mapping = {
        "binance": "Binance",
        "hyperliquid": "Hyperliquid",
        "bybit": "Bybit",
        "okx": "OKX",
        "bitget": "Bitget",
        "gate": "Gate",
    }
    value = str(exchange or "Binance").strip()
    return mapping.get(value.lower(), value)


def _coin_and_pair(symbol: str | None) -> tuple[str, str]:
    coin = str(symbol or "BTC").upper().strip().replace("/", "")
    for suffix in ("USDT", "USD", "PERP"):
        if coin.endswith(suffix) and len(coin) > len(suffix):
            coin = coin[: -len(suffix)]
            break
    return coin or "BTC", f"{coin or 'BTC'}USDT"


def _event_contract_required_plan(period: str, current_plan: str | None) -> str | None:
    minutes = INTERVAL_MINUTES.get(period)
    if minutes is None:
        return None
    current_plan = _normalize_plan(current_plan)
    if minutes < 30:
        return "Standard"
    if current_plan == "Hobbyist" and minutes < 240:
        return "Startup"
    return None


def _cached_event_contract_capability(cache_key: str) -> dict[str, Any] | None:
    cached = _event_contract_capability_cache.get(cache_key)
    if not cached:
        return None
    created_at, payload = cached
    if time.time() - created_at > CAPABILITY_CACHE_TTL_SECONDS:
        _event_contract_capability_cache.pop(cache_key, None)
        return None
    return payload


def _store_event_contract_capability(cache_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    _event_contract_capability_cache[cache_key] = (time.time(), payload)
    return payload


def event_contract_interval_blocked(failed_metrics: list[dict[str, Any]]) -> bool:
    return any(
        "interval" in str(item.get("message") or "").lower()
        and "plan" in str(item.get("message") or "").lower()
        for item in failed_metrics
    )
