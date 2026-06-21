from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth_dependencies import get_current_user
from config.settings import COINGLASS_API_BASE_URL, COINGLASS_API_KEY
from database.connection import get_db
from database.models import CoinGlassUserKey, User
from utils.encryption import decrypt_private_key, encrypt_private_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coinglass", tags=["coinglass"])

DOC_ROOT = Path(__file__).resolve().parents[2] / "CoinGlass API 介绍"
PLAN_ORDER = ["Hobbyist", "Startup", "Standard", "Professional", "Enterprise"]
INTERVAL_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "6h": 360,
    "8h": 480,
    "12h": 720,
    "1d": 1440,
    "1w": 10080,
}


CURATED_DATASETS: dict[str, dict[str, Any]] = {
    "pairs_markets": {
        "label": "Pairs Markets",
        "category": "价格与市场",
        "path": "/api/futures/pairs-markets",
        "default_params": {"symbol": "BTC"},
        "focus": "market",
    },
    "price_history": {
        "label": "Price History",
        "category": "价格与市场",
        "path": "/api/futures/price/history",
        "default_params": {"exchange": "Binance", "symbol": "BTCUSDT", "interval": "30m", "limit": "120"},
        "focus": "ohlc",
    },
    "aggregated_cvd": {
        "label": "Aggregated CVD",
        "category": "主动买卖",
        "path": "/api/futures/aggregated-cvd/history",
        "default_params": {"exchange_list": "Binance", "symbol": "BTC", "interval": "30m", "limit": "120"},
        "focus": "flow",
    },
    "pair_taker_volume": {
        "label": "Pair Taker Buy/Sell",
        "category": "主动买卖",
        "path": "/api/futures/v2/taker-buy-sell-volume/history",
        "default_params": {"exchange": "Binance", "symbol": "BTCUSDT", "interval": "30m", "limit": "120"},
        "focus": "flow",
    },
    "coin_taker_volume": {
        "label": "Coin Taker Buy/Sell",
        "category": "主动买卖",
        "path": "/api/futures/aggregated-taker-buy-sell-volume/history",
        "default_params": {"exchange_list": "Binance", "symbol": "BTC", "interval": "30m", "limit": "120"},
        "focus": "flow",
    },
    "coin_netflow": {
        "label": "Coin Netflow",
        "category": "主动买卖",
        "path": "/api/futures/coin/netflow",
        "default_params": {"exchange_list": "Binance", "symbol": "BTC"},
        "focus": "flow",
    },
    "open_interest": {
        "label": "Aggregated Open Interest",
        "category": "持仓量",
        "path": "/api/futures/open-interest/aggregated-history",
        "default_params": {"symbol": "BTC", "interval": "30m", "limit": "120"},
        "focus": "interest",
    },
    "global_long_short": {
        "label": "Global Long/Short",
        "category": "多空比",
        "path": "/api/futures/global-long-short-account-ratio/history",
        "default_params": {"exchange": "Binance", "symbol": "BTCUSDT", "interval": "30m", "limit": "120"},
        "focus": "ratio",
    },
    "funding_rate": {
        "label": "Funding Rate",
        "category": "资金费率",
        "path": "/api/futures/funding-rate/history",
        "default_params": {"exchange": "Binance", "symbol": "BTCUSDT", "interval": "30m", "limit": "120"},
        "focus": "funding",
    },
    "pair_liquidation": {
        "label": "Pair Liquidation",
        "category": "爆仓与清算",
        "path": "/api/futures/liquidation/history",
        "default_params": {"exchange": "Binance", "symbol": "BTCUSDT", "interval": "30m", "limit": "120"},
        "focus": "liquidation",
    },
    "coin_liquidation": {
        "label": "Coin Liquidation",
        "category": "爆仓与清算",
        "path": "/api/futures/liquidation/aggregated-history",
        "default_params": {"exchange_list": "Binance", "symbol": "BTC", "interval": "30m", "limit": "120"},
        "focus": "liquidation",
    },
    "liquidation_orders": {
        "label": "Liquidation Orders",
        "category": "爆仓与清算",
        "path": "/api/futures/liquidation/order",
        "default_params": {"exchange": "Binance", "symbol": "BTC", "min_liquidation_amount": "10000"},
        "focus": "liquidation",
    },
    "orderbook_depth": {
        "label": "Orderbook Bid/Ask",
        "category": "订单薄(L2)",
        "path": "/api/futures/orderbook/ask-bids-history",
        "default_params": {"exchange": "Binance", "symbol": "BTCUSDT", "interval": "30m", "limit": "120", "range": "1"},
        "focus": "orderbook",
    },
    "fear_greed": {
        "label": "Fear & Greed",
        "category": "其他",
        "path": "/api/index/fear-greed-history",
        "default_params": {},
        "focus": "index",
    },
}

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


class CoinGlassKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=16, max_length=200)


def _clean_cell(value: str) -> str:
    return (
        value.replace("\u200b", "")
        .replace("`", "")
        .replace("&gt;", ">")
        .replace("&lt;", "<")
        .strip()
    )


def _endpoint_id(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:12]


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _parse_plan_info(text: str) -> dict[str, Any]:
    availability = {plan: None for plan in PLAN_ORDER}
    interval_limit: dict[str, str | None] = {plan: None for plan in PLAN_ORDER}

    available_match = re.search(r"^\|\s*Available\s*\|(.+)$", text, flags=re.MULTILINE)
    if available_match:
        cells = [_clean_cell(cell) for cell in available_match.group(1).split("|")[: len(PLAN_ORDER)]]
        for plan, cell in zip(PLAN_ORDER, cells):
            if "✅" in cell:
                availability[plan] = True
            elif "❌" in cell:
                availability[plan] = False

    required_level_match = re.search(r"Required Account Level:\s*([A-Za-z]+)", text, flags=re.IGNORECASE)
    if required_level_match:
        required = required_level_match.group(1).capitalize()
        if required in PLAN_ORDER:
            required_index = PLAN_ORDER.index(required)
            availability = {plan: idx >= required_index for idx, plan in enumerate(PLAN_ORDER)}

    interval_match = re.search(r"^\|\s*interval Limit\s*\|(.+)$", text, flags=re.IGNORECASE | re.MULTILINE)
    if interval_match:
        cells = [_clean_cell(cell) for cell in interval_match.group(1).split("|")[: len(PLAN_ORDER)]]
        for plan, cell in zip(PLAN_ORDER, cells):
            interval_limit[plan] = cell or None

    min_plan = None
    for plan in PLAN_ORDER:
        if availability.get(plan) is True:
            min_plan = plan
            break

    return {
        "availability": availability,
        "min_plan": min_plan,
        "interval_limit": interval_limit,
    }


def _parse_params(path_block: str) -> list[dict[str, Any]]:
    lines = path_block.splitlines()
    params: list[dict[str, Any]] = []

    for index, line in enumerate(lines):
        name_match = re.search(r'"name"\s*:\s*"([^"]+)"', line)
        if not name_match:
            continue

        name = name_match.group(1)
        if name == "CG-API-KEY":
            continue

        segment = "\n".join(lines[index : index + 24])
        in_match = re.search(r'"in"\s*:\s*"([^"]+)"', segment)
        type_match = re.search(r'"type"\s*:\s*"([^"]+)"', segment)
        default_match = re.search(r'"default"\s*:\s*("([^"]*)"|[-0-9.]+|true|false)', segment)
        description_match = re.search(r'"description"\s*:\s*"([^"]*)"', segment)

        params.append(
            {
                "name": name,
                "in": in_match.group(1) if in_match else "query",
                "required": bool(re.search(r'"required"\s*:\s*true', segment)),
                "type": type_match.group(1) if type_match else "string",
                "default": default_match.group(2) if default_match and default_match.group(2) is not None else (
                    default_match.group(1) if default_match else None
                ),
                "description": description_match.group(1) if description_match else "",
            }
        )

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for param in params:
        if param["name"] in seen:
            continue
        seen.add(param["name"])
        unique.append(param)
    return unique


def _parse_doc_file(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    rel_path = path.relative_to(DOC_ROOT).as_posix()
    category = rel_path.split("/", 1)[0] if "/" in rel_path else "General"
    title = _extract_title(text, path.stem)
    plan = _parse_plan_info(text)

    path_matches = list(re.finditer(r'"(/api/[^"]+)"\s*:\s*\{', text))
    if not path_matches and category == "WebSocket":
        return [
            {
                "id": hashlib.sha1(f"{rel_path}:{title}".encode("utf-8")).hexdigest()[:12],
                "title": title,
                "category": category,
                "path": "wss://open-ws.coinglass.com/ws-api",
                "method": "WS",
                "summary": title,
                "description": "",
                "operation_id": "",
                "params": [],
                "required_params": [],
                "min_plan": plan["min_plan"],
                "availability": plan["availability"],
                "interval_limit": plan["interval_limit"],
                "doc_path": rel_path,
            }
        ]

    endpoints: list[dict[str, Any]] = []
    for idx, match in enumerate(path_matches):
        api_path = match.group(1)
        next_start = path_matches[idx + 1].start() if idx + 1 < len(path_matches) else len(text)
        block = text[match.start() : next_start]

        summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', block)
        description_match = re.search(r'"description"\s*:\s*"([^"]+)"', block)
        operation_match = re.search(r'"operationId"\s*:\s*"([^"]+)"', block)
        method = "GET" if re.search(r'"\s*get\s*"\s*:', block, flags=re.IGNORECASE) else "GET"

        endpoints.append(
            {
                "id": _endpoint_id(api_path),
                "title": title,
                "category": category,
                "path": api_path,
                "method": method,
                "summary": summary_match.group(1) if summary_match else title,
                "description": description_match.group(1) if description_match else "",
                "operation_id": operation_match.group(1) if operation_match else "",
                "params": _parse_params(block),
                "required_params": [p["name"] for p in _parse_params(block) if p.get("required")],
                "min_plan": plan["min_plan"],
                "availability": plan["availability"],
                "interval_limit": plan["interval_limit"],
                "doc_path": rel_path,
            }
        )

    return endpoints


@lru_cache(maxsize=1)
def _catalog() -> list[dict[str, Any]]:
    if not DOC_ROOT.exists():
        return []

    endpoints_by_path: dict[str, dict[str, Any]] = {}
    for doc_file in sorted(DOC_ROOT.rglob("*.md")):
        rel = doc_file.relative_to(DOC_ROOT).as_posix()
        if rel.startswith("_旧版本") or rel in {"README.md", "秘钥.md", "客户功能需求，禁止修改.md"}:
            continue
        for endpoint in _parse_doc_file(doc_file):
            key = endpoint["path"] if str(endpoint["path"]).startswith("/api/") else endpoint["id"]
            endpoints_by_path.setdefault(key, endpoint)

    return sorted(endpoints_by_path.values(), key=lambda item: (item["category"], item["title"], item["path"]))


def _catalog_by_id() -> dict[str, dict[str, Any]]:
    return {endpoint["id"]: endpoint for endpoint in _catalog()}


def _catalog_by_path() -> dict[str, dict[str, Any]]:
    return {endpoint["path"]: endpoint for endpoint in _catalog()}


def _server_coinglass_key() -> str:
    return (COINGLASS_API_KEY or os.getenv("COINGLASS_API_KEY", "")).strip()


def _mask_key(api_key: str) -> str:
    if len(api_key) <= 10:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"


def _user_key_record(db: Session, user_id: int) -> CoinGlassUserKey | None:
    return db.query(CoinGlassUserKey).filter(CoinGlassUserKey.user_id == user_id).first()


def _decrypt_user_key(record: CoinGlassUserKey) -> str:
    try:
        return decrypt_private_key(record.api_key_encrypted)
    except Exception as exc:
        logger.warning("Failed to decrypt CoinGlass key for user_id=%s", record.user_id)
        raise HTTPException(status_code=500, detail="Stored CoinGlass API key cannot be decrypted") from exc


def _effective_key(db: Session, user: User) -> tuple[str, str, str | None]:
    record = _user_key_record(db, user.id)
    if record:
        api_key = _decrypt_user_key(record)
        return api_key, "user", record.key_masked

    server_key = _server_coinglass_key()
    if server_key:
        return server_key, "server", _mask_key(server_key)

    return "", "none", None


def _coinglass_request(
    path: str,
    params: dict[str, Any],
    *,
    api_key: str | None = None,
    key_source: str = "server",
    key_masked: str | None = None,
) -> dict[str, Any]:
    api_key = (api_key or _server_coinglass_key()).strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="COINGLASS_API_KEY is not configured")

    if path != "/api/user/account/subscription" and path not in _catalog_by_path():
        raise HTTPException(status_code=404, detail="CoinGlass endpoint is not in the local documentation catalog")

    cleaned_params = {
        key: value
        for key, value in params.items()
        if value is not None and str(value).strip() != ""
    }
    url = f"{COINGLASS_API_BASE_URL.rstrip('/')}{path}"
    try:
        response = requests.get(
            url,
            headers={"CG-API-KEY": api_key, "accept": "application/json"},
            params=cleaned_params,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("CoinGlass request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CoinGlass request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="CoinGlass returned a non-JSON response") from exc

    rate_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower().startswith("x-ratelimit") or key.lower() in {"retry-after"}
    }

    return {
        "ok": response.ok and str(payload.get("code", "0")) == "0",
        "status_code": response.status_code,
        "path": path,
        "params": cleaned_params,
        "payload": payload,
        "data": payload.get("data") if isinstance(payload, dict) else None,
        "msg": payload.get("msg") if isinstance(payload, dict) else None,
        "rate_limit": rate_headers,
        "key_source": key_source,
        "key_masked": key_masked or _mask_key(api_key),
        "fetched_at": int(time.time() * 1000),
    }


def _plan_index(plan: str | None) -> int:
    plan = _normalize_plan(plan)
    if not plan or plan not in PLAN_ORDER:
        return -1
    return PLAN_ORDER.index(plan)


def _normalize_plan(plan: str | None) -> str | None:
    if not plan:
        return None
    value = str(plan).strip()
    return next((item for item in PLAN_ORDER if item.lower() == value.lower()), value.title())


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


def _interval_allowed(plan: str | None, interval: str | None, interval_limit: dict[str, str | None]) -> bool:
    plan = _normalize_plan(plan)
    if not plan or not interval:
        return True
    limit = interval_limit.get(plan)
    if not limit or "No Limit" in limit:
        return True
    match = re.search(r">=\s*([0-9]+)([mh])", limit)
    if not match:
        return True
    value = int(match.group(1))
    unit = match.group(2)
    required_minutes = value if unit == "m" else value * 60
    return INTERVAL_MINUTES.get(interval, required_minutes) >= required_minutes


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


def _merge_params(defaults: dict[str, Any], supplied: dict[str, Any], allowed_names: set[str]) -> dict[str, Any]:
    merged = dict(defaults)
    for key, value in supplied.items():
        if key in allowed_names:
            merged[key] = value
    return merged


@router.get("/catalog")
def get_catalog():
    endpoints = _catalog()
    categories: dict[str, dict[str, Any]] = {}
    for endpoint in endpoints:
        category = endpoint["category"]
        entry = categories.setdefault(
            category,
            {"name": category, "count": 0, "startup_available": 0, "standard_plus": 0},
        )
        entry["count"] += 1
        if endpoint.get("availability", {}).get("Startup") is True:
            entry["startup_available"] += 1
        if _plan_index(endpoint.get("min_plan")) >= _plan_index("Standard"):
            entry["standard_plus"] += 1

    return {
        "base_url": COINGLASS_API_BASE_URL,
        "total": len(endpoints),
        "categories": sorted(categories.values(), key=lambda item: item["name"]),
        "endpoints": endpoints,
        "datasets": [
            {
                "id": dataset_id,
                **definition,
                "endpoint_id": _endpoint_id(definition["path"]),
                "endpoint": _catalog_by_path().get(definition["path"]),
            }
            for dataset_id, definition in CURATED_DATASETS.items()
        ],
    }


@router.get("/subscription")
def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    api_key, key_source, key_masked = _effective_key(db, current_user)
    if not api_key:
        return {
            "configured": False,
            "user_key_configured": False,
            "server_key_configured": False,
            "key_source": "none",
            "key_masked": None,
            "level": None,
            "expired": None,
            "expire_time": None,
        }

    result = _coinglass_request(
        "/api/user/account/subscription",
        {},
        api_key=api_key,
        key_source=key_source,
        key_masked=key_masked,
    )
    data = result.get("data") or {}
    record = _user_key_record(db, current_user.id)
    return {
        "configured": True,
        "user_key_configured": record is not None,
        "server_key_configured": bool(_server_coinglass_key()),
        "key_source": key_source,
        "key_masked": key_masked,
        "ok": result["ok"],
        "level": data.get("level"),
        "expired": data.get("expired"),
        "expire_time": data.get("expire_time"),
        "fetched_at": result["fetched_at"],
    }


@router.get("/event-contract-capability")
def get_event_contract_capability(
    symbol: str = "BTC",
    exchange: str = "Binance",
    period: str = "1m",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = str(period or "1m")
    if period not in INTERVAL_MINUTES:
        return {
            "available": False,
            "configured": False,
            "status": "unsupported_period",
            "reason": f"Unsupported CoinGlass interval for event-contract checks: {period}",
            "period": period,
            "metrics": [],
        }

    api_key, key_source, key_masked = _effective_key(db, current_user)
    if not api_key:
        return {
            "available": False,
            "configured": False,
            "status": "not_configured",
            "reason": "CoinGlass API key is not configured.",
            "period": period,
            "key_source": "none",
            "key_masked": None,
            "metrics": [],
        }

    cache_key = hashlib.sha1(
        f"{api_key}:{symbol}:{exchange}:{period}".encode("utf-8")
    ).hexdigest()
    cached = _cached_event_contract_capability(cache_key)
    if cached:
        return cached

    subscription_result = _coinglass_request(
        "/api/user/account/subscription",
        {},
        api_key=api_key,
        key_source=key_source,
        key_masked=key_masked,
    )
    subscription_data = subscription_result.get("data") or {}
    plan = _normalize_plan(subscription_data.get("level"))
    expired = bool(subscription_data.get("expired"))
    base_payload: dict[str, Any] = {
        "available": False,
        "configured": True,
        "period": period,
        "symbol": symbol,
        "exchange": _coinglass_exchange_name(exchange),
        "key_source": key_source,
        "key_masked": key_masked,
        "level": plan,
        "expired": expired,
        "expire_time": subscription_data.get("expire_time"),
        "required_plan": _event_contract_required_plan(period, plan),
        "fetched_at": int(time.time() * 1000),
    }

    if not subscription_result.get("ok"):
        base_payload.update(
            {
                "status": "subscription_check_failed",
                "reason": subscription_result.get("msg") or "CoinGlass subscription check failed.",
                "metrics": [],
            }
        )
        return _store_event_contract_capability(cache_key, base_payload)

    if expired:
        base_payload.update(
            {
                "status": "expired",
                "reason": "CoinGlass subscription is expired.",
                "metrics": [],
            }
        )
        return _store_event_contract_capability(cache_key, base_payload)

    coin, pair = _coin_and_pair(symbol)
    exchange_name = _coinglass_exchange_name(exchange)
    metrics = []
    for metric in EVENT_CONTRACT_REQUIRED_METRICS:
        params = metric["params"](coin, pair, exchange_name, period)
        result = _coinglass_request(
            metric["path"],
            params,
            api_key=api_key,
            key_source=key_source,
            key_masked=key_masked,
        )
        metrics.append(
            {
                "metric": metric["metric"],
                "label": metric["label"],
                "path": metric["path"],
                "ok": bool(result.get("ok")),
                "status_code": result.get("status_code"),
                "code": (result.get("payload") or {}).get("code"),
                "message": result.get("msg") or (result.get("payload") or {}).get("message"),
            }
        )

    failed = [item for item in metrics if not item["ok"]]
    interval_blocked = any(
        "interval" in str(item.get("message") or "").lower()
        and "plan" in str(item.get("message") or "").lower()
        for item in failed
    )
    if failed:
        reason = (
            f"Current CoinGlass plan {plan or '-'} does not support {period} event-contract metrics."
            if interval_blocked
            else "; ".join(f"{item['label']}: {item.get('message') or item.get('code')}" for item in failed)
        )
        base_payload.update(
            {
                "available": False,
                "status": "plan_interval_unavailable" if interval_blocked else "metric_unavailable",
                "reason": reason,
                "metrics": metrics,
            }
        )
        return _store_event_contract_capability(cache_key, base_payload)

    base_payload.update(
        {
            "available": True,
            "status": "available",
            "reason": f"CoinGlass {period} event-contract metrics are available for plan {plan or '-'}",
            "metrics": metrics,
        }
    )
    return _store_event_contract_capability(cache_key, base_payload)


@router.post("/key")
def save_user_key(
    body: CoinGlassKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    api_key = body.api_key.strip()
    result = _coinglass_request(
        "/api/user/account/subscription",
        {},
        api_key=api_key,
        key_source="user",
        key_masked=_mask_key(api_key),
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("msg") or "CoinGlass API key validation failed")

    data = result.get("data") or {}
    record = _user_key_record(db, current_user.id)
    if record:
        record.api_key_encrypted = encrypt_private_key(api_key)
        record.key_masked = _mask_key(api_key)
        record.plan_level = data.get("level")
        record.expire_time = data.get("expire_time")
        record.expired = data.get("expired")
        record.last_validated_at = datetime.utcnow()
    else:
        record = CoinGlassUserKey(
            user_id=current_user.id,
            api_key_encrypted=encrypt_private_key(api_key),
            key_masked=_mask_key(api_key),
            plan_level=data.get("level"),
            expire_time=data.get("expire_time"),
            expired=data.get("expired"),
            last_validated_at=datetime.utcnow(),
        )
        db.add(record)
    db.commit()

    return {
        "configured": True,
        "user_key_configured": True,
        "server_key_configured": bool(_server_coinglass_key()),
        "key_source": "user",
        "key_masked": _mask_key(api_key),
        "ok": result["ok"],
        "level": data.get("level"),
        "expired": data.get("expired"),
        "expire_time": data.get("expire_time"),
        "fetched_at": result["fetched_at"],
    }


@router.delete("/key")
def delete_user_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _user_key_record(db, current_user.id)
    if record:
        db.delete(record)
        db.commit()
    return get_subscription(current_user=current_user, db=db)


@router.get("/dataset/{dataset_id}")
def get_dataset(
    dataset_id: str,
    symbol: str | None = None,
    exchange: str | None = None,
    exchange_list: str | None = None,
    interval: str | None = None,
    limit: int | None = Query(None, ge=1, le=1000),
    start_time: int | None = None,
    end_time: int | None = None,
    unit: str | None = None,
    range: str | None = Query(None),
    min_liquidation_amount: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset = CURATED_DATASETS.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Unknown CoinGlass dataset")

    endpoint = _catalog_by_path().get(dataset["path"])
    allowed_names = {param["name"] for param in endpoint.get("params", [])} if endpoint else set(dataset["default_params"].keys())
    params = _merge_params(
        dataset["default_params"],
        {
            "symbol": symbol,
            "exchange": exchange,
            "exchange_list": exchange_list,
            "interval": interval,
            "limit": limit,
            "start_time": start_time,
            "end_time": end_time,
            "unit": unit,
            "range": range,
            "min_liquidation_amount": min_liquidation_amount,
        },
        allowed_names,
    )

    api_key, key_source, key_masked = _effective_key(db, current_user)
    result = _coinglass_request(dataset["path"], params, api_key=api_key, key_source=key_source, key_masked=key_masked)
    result["dataset"] = {"id": dataset_id, **dataset, "endpoint": endpoint}
    current_plan = None
    try:
        current_plan = _coinglass_request(
            "/api/user/account/subscription",
            {},
            api_key=api_key,
            key_source=key_source,
            key_masked=key_masked,
        ).get("data", {}).get("level")
    except Exception:
        current_plan = None
    if endpoint:
        result["plan_check"] = {
            "current_plan": current_plan,
            "min_plan": endpoint.get("min_plan"),
            "interval_allowed": _interval_allowed(
                current_plan.title() if isinstance(current_plan, str) else current_plan,
                params.get("interval"),
                endpoint.get("interval_limit", {}),
            ),
        }
    return result


@router.get("/endpoint/{endpoint_id}")
def get_endpoint_data(
    endpoint_id: str,
    symbol: str | None = None,
    exchange: str | None = None,
    exchange_list: str | None = None,
    interval: str | None = None,
    limit: int | None = Query(None, ge=1, le=1000),
    start_time: int | None = None,
    end_time: int | None = None,
    unit: str | None = None,
    range: str | None = Query(None),
    min_liquidation_amount: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    endpoint = _catalog_by_id().get(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Unknown CoinGlass endpoint")

    allowed_names = {param["name"] for param in endpoint.get("params", [])}
    defaults = {
        param["name"]: param.get("default")
        for param in endpoint.get("params", [])
        if param.get("default") not in (None, "")
    }
    params = _merge_params(
        defaults,
        {
            "symbol": symbol,
            "exchange": exchange,
            "exchange_list": exchange_list,
            "interval": interval,
            "limit": limit,
            "start_time": start_time,
            "end_time": end_time,
            "unit": unit,
            "range": range,
            "min_liquidation_amount": min_liquidation_amount,
        },
        allowed_names,
    )

    missing = [name for name in endpoint.get("required_params", []) if not params.get(name)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required query params: {', '.join(missing)}")

    api_key, key_source, key_masked = _effective_key(db, current_user)
    result = _coinglass_request(endpoint["path"], params, api_key=api_key, key_source=key_source, key_masked=key_masked)
    result["endpoint"] = endpoint
    current_plan = None
    try:
        current_plan = _coinglass_request(
            "/api/user/account/subscription",
            {},
            api_key=api_key,
            key_source=key_source,
            key_masked=key_masked,
        ).get("data", {}).get("level")
    except Exception:
        current_plan = None
    result["plan_check"] = {
        "current_plan": current_plan,
        "min_plan": endpoint.get("min_plan"),
        "interval_allowed": _interval_allowed(
            current_plan.title() if isinstance(current_plan, str) else current_plan,
            params.get("interval"),
            endpoint.get("interval_limit", {}),
        ),
    }
    return result
