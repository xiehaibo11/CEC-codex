"""Strategy Radar S2S tools for Hyper AI."""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy.orm import Session

from database.models import SystemConfig

logger = logging.getLogger(__name__)

_STRATEGY_RADAR_UNIVERSE_CACHE: dict[str, Any] = {"expires_at": None, "payload": None}


def _get_hyper_insight_access_token(db: Session) -> str:
    token_row = db.query(SystemConfig).filter(SystemConfig.key == "hyper_insight_wallet_access_token").first()
    return ((token_row.value if token_row else "") or "").strip()


def _strategy_radar_headers(db: Session) -> dict[str, str] | None:
    access_token = _get_hyper_insight_access_token(db)
    if not access_token:
        return None
    return {"Authorization": f"Bearer {access_token}"}


def _strategy_radar_base_url() -> str:
    return os.getenv("HYPER_INSIGHT_API_BASE_URL", "https://hyper.akooi.com").rstrip("/")


def _fetch_strategy_radar_universe(db: Session, *, force_refresh: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    cached_until = _STRATEGY_RADAR_UNIVERSE_CACHE.get("expires_at")
    cached_payload = _STRATEGY_RADAR_UNIVERSE_CACHE.get("payload")
    if (
        not force_refresh
        and cached_payload is not None
        and isinstance(cached_until, datetime)
        and cached_until > now
    ):
        return cached_payload

    headers = _strategy_radar_headers(db)
    if headers is None:
        return {
            "ok": False,
            "error": "Please log in to CEC-codex before using Strategy Radar with Hyper AI.",
            "reason": "missing_login_token",
            "next_steps": [
                "Log in to CEC-codex with your linked account first.",
                "After login, ask Hyper AI to search Strategy Radar again.",
            ],
        }

    url = f"{_strategy_radar_base_url()}/api/s2s/strategy-radar/universe"
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 401:
        return {
            "ok": False,
            "error": "Your Hyper Insight login in CEC-codex is no longer valid.",
            "reason": "upstream_401",
            "next_steps": [
                "Log in to CEC-codex again.",
                "After login, ask Hyper AI to search Strategy Radar again.",
            ],
        }
    if response.status_code in {403, 503}:
        return {
            "ok": False,
            "error": "Strategy Radar lookup is temporarily unavailable right now.",
            "reason": f"upstream_{response.status_code}",
        }
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        payload["ok"] = True
        _STRATEGY_RADAR_UNIVERSE_CACHE["payload"] = payload
        _STRATEGY_RADAR_UNIVERSE_CACHE["expires_at"] = now + timedelta(minutes=10)
        return payload
    return {"ok": False, "error": "Strategy Radar returned an invalid universe response."}


def execute_get_strategy_radar_universe(db: Session) -> str:
    """Return Strategy Radar's currently queryable symbol/period/regime combinations."""
    try:
        payload = _fetch_strategy_radar_universe(db)
        return json.dumps(payload, indent=2, ensure_ascii=False)
    except requests.RequestException as exc:
        logger.error("[strategy_radar_universe] Error: %s", exc)
        return json.dumps({
            "ok": False,
            "error": "Failed to fetch Strategy Radar supported symbols right now.",
        }, ensure_ascii=False)


def _universe_supports(universe: dict, *, symbol: str, period: str, exchange: str | None) -> tuple[bool, dict | None]:
    for item in universe.get("symbols") or []:
        if str(item.get("symbol", "")).upper() != symbol:
            continue
        for period_item in item.get("periods") or []:
            if period_item.get("period") != period:
                continue
            if exchange and period_item.get("exchange") != exchange:
                continue
            return True, period_item
        return False, None
    return False, None


def execute_search_strategy_radar(
    db: Session,
    *,
    symbol: str,
    period: str = "1h",
    regime: str | None = None,
    exchange: str | None = None,
    strategy_type: str | None = None,
    sort_by: str | None = None,
    risk_level: str | None = None,
    timeframe: str | None = None,
    limit: int = 5,
) -> str:
    """Search protected Strategy Radar S2S endpoints for current strategy candidates."""
    safe_symbol = (symbol or "").strip().upper()
    safe_period = period if period in {"1h", "4h", "1d"} else "1h"
    safe_exchange = exchange if exchange in {"hyperliquid", "binance"} else None
    safe_sort_by = sort_by if sort_by in {"relevance", "quality", "newest"} else None
    safe_risk_level = risk_level if risk_level in {"Low", "Medium", "High"} else None
    safe_timeframe = timeframe if timeframe in {"1h", "4h", "1d", "multi"} else None
    safe_limit = max(1, min(int(limit or 5), 10))

    if not safe_symbol:
        return json.dumps({"ok": False, "error": "symbol is required"}, ensure_ascii=False)

    universe = _fetch_strategy_radar_universe(db)
    if not universe.get("ok"):
        return json.dumps(universe, ensure_ascii=False)

    supported, period_item = _universe_supports(
        universe,
        symbol=safe_symbol,
        period=safe_period,
        exchange=safe_exchange,
    )
    if not supported:
        return json.dumps({
            "ok": False,
            "reason": "unsupported_symbol_period",
            "symbol": safe_symbol,
            "period": safe_period,
            "exchange": safe_exchange,
            "supported_symbols": [
                item.get("symbol") for item in (universe.get("symbols") or []) if item.get("symbol")
            ],
            "usage_note": "Only combinations returned by get_strategy_radar_universe are supported.",
        }, ensure_ascii=False)

    headers = _strategy_radar_headers(db)
    if headers is None:
        return json.dumps({
            "ok": False,
            "error": "Please log in to CEC-codex before using Strategy Radar with Hyper AI.",
            "next_steps": [
                "Log in to CEC-codex with your linked account first.",
                "After login, ask Hyper AI to search Strategy Radar again.",
            ],
        }, ensure_ascii=False)

    params = {
        "symbol": safe_symbol,
        "period": safe_period,
        "limit": safe_limit,
    }
    if regime:
        params["regime"] = regime
    if safe_exchange:
        params["exchange"] = safe_exchange
    if strategy_type:
        params["strategy_type"] = strategy_type
    if safe_sort_by:
        params["sort_by"] = safe_sort_by
    if safe_risk_level:
        params["risk_level"] = safe_risk_level
    if safe_timeframe:
        params["timeframe"] = safe_timeframe

    try:
        response = requests.get(
            f"{_strategy_radar_base_url()}/api/s2s/strategy-radar/search",
            headers=headers,
            params=params,
            timeout=12,
        )
        if response.status_code == 401:
            return json.dumps({
                "ok": False,
                "error": "Your Hyper Insight login in CEC-codex is no longer valid.",
                "reason": "upstream_401",
                "next_steps": [
                    "Log in to CEC-codex again.",
                    "After login, ask Hyper AI to search Strategy Radar again.",
                ],
            }, ensure_ascii=False)
        if response.status_code in {403, 503}:
            return json.dumps({
                "ok": False,
                "error": "Strategy Radar lookup is temporarily unavailable right now.",
                "reason": f"upstream_{response.status_code}",
            }, ensure_ascii=False)
        if response.status_code == 429:
            return json.dumps({
                "ok": False,
                "error": "Strategy Radar is rate limited right now. Please retry later.",
            }, ensure_ascii=False)
        response.raise_for_status()
        payload = response.json()
        return json.dumps(payload, indent=2, ensure_ascii=False)
    except requests.RequestException as exc:
        logger.error("[search_strategy_radar] Error: %s", exc)
        return json.dumps({
            "ok": False,
            "error": "Failed to fetch Strategy Radar candidates right now.",
        }, ensure_ascii=False)
