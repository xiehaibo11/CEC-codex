from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import COINGLASS_API_BASE_URL

DOC_ROOT = Path(__file__).resolve().parents[3] / "CoinGlass API 介绍"
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
        params = _parse_params(block)

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
                "params": params,
                "required_params": [param["name"] for param in params if param.get("required")],
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


def _normalize_plan(plan: str | None) -> str | None:
    if not plan:
        return None
    value = str(plan).strip()
    return next((item for item in PLAN_ORDER if item.lower() == value.lower()), value.title())


def _plan_index(plan: str | None) -> int:
    plan = _normalize_plan(plan)
    if not plan or plan not in PLAN_ORDER:
        return -1
    return PLAN_ORDER.index(plan)


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


def _merge_params(defaults: dict[str, Any], supplied: dict[str, Any], allowed_names: set[str]) -> dict[str, Any]:
    merged = dict(defaults)
    for key, value in supplied.items():
        if key in allowed_names:
            merged[key] = value
    return merged


def get_catalog_payload() -> dict[str, Any]:
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
