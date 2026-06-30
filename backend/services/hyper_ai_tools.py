"""
Hyper AI Tools - Tools for Hyper AI main agent

Provides tools for:
- System overview and diagnostics
- Wallet status queries
- API reference documentation
- Market data (klines, regime, flow)
- Create/save operations (signal pool, prompt, program, AI trader)
- Sub-agent calls (Prompt AI, Program AI, Signal AI, Attribution AI)
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

import requests
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database.models import SystemConfig
from services.hyper_ai_subagents import SUBAGENT_TOOLS, execute_subagent_tool

# Tool schema catalog (split by responsibility into sibling modules)
from services.hyper_ai_tool_schemas import OPERATION_TOOL_SCHEMAS
from services.hyper_ai_tool_schemas_management import (
    MANAGEMENT_TOOL_SCHEMAS,
    EXTERNAL_TOOLS,
    SKILL_TOOLS,
)

# Tool execution handlers (split by responsibility into sibling modules)
from services.hyper_ai_tools_queries import (
    execute_get_system_overview,
    execute_get_wallet_status,
    execute_get_api_reference,
    execute_get_klines,
    execute_get_market_regime,
    execute_get_market_flow,
    execute_get_system_logs,
    execute_get_contact_config,
    execute_get_trading_environment,
    execute_get_watchlist,
    execute_update_watchlist,
)
from services.hyper_ai_tools_diagnostics import execute_diagnose_trader_issues
from services.hyper_ai_tools_writes import (
    execute_save_signal_pool,
    execute_save_prompt,
    execute_save_program,
    execute_create_ai_trader,
    execute_save_memory,
)
from services.hyper_ai_tools_resources import (
    execute_list_traders,
    execute_get_prompt_backtests,
    execute_predict_event_contract_5m,
    execute_run_event_contract_backtest,
    execute_list_signal_pools,
)
from services.hyper_ai_tools_bindings import (
    execute_bind_prompt_to_trader,
    execute_bind_program_to_trader,
    execute_update_trader_strategy,
    execute_update_ai_trader,
    execute_update_program_binding,
    execute_update_signal_pool,
    execute_update_prompt_binding,
)
from services.hyper_ai_tools_factors import (
    execute_query_factors,
    execute_evaluate_factor,
    execute_save_factor,
    execute_edit_factor,
    execute_compute_factor,
    execute_get_factor_functions,
)
from services.hyper_ai_tools_web import execute_web_search, execute_fetch_url

logger = logging.getLogger(__name__)


# Tool definitions in OpenAI format
# IMPORTANT: When adding/removing/modifying tools, you MUST also update:
#   1. The JSON schema definitions (hyper_ai_tool_schemas*.py)
#   2. The execute_xxx() implementation function (hyper_ai_tools_*.py)
#   3. The execute_hyper_ai_tool() dispatcher (hyper_ai_tools_dispatch.py)
#   4. The system prompt: backend/config/hyper_ai_system_prompt.md (Available Tools section)
# Combine base tools + external tools + skill tools + sub-agent tools
HYPER_AI_TOOLS = (
    OPERATION_TOOL_SCHEMAS
    + MANAGEMENT_TOOL_SCHEMAS
    + EXTERNAL_TOOLS
    + SKILL_TOOLS
    + SUBAGENT_TOOLS
)


# =============================================================================
# Wallet & strategy tracking tools (CoinGlass + Strategy Radar)
# These handlers are kept in this module because external static checks index
# this file's source text directly (see tests/test_signal_wallet_tracking_*).
# =============================================================================

COINGLASS_WALLET_TRACKING_ENDPOINTS = (
    ("whale_position", "/api/hyperliquid/whale-position", {}),
    ("whale_alert", "/api/hyperliquid/whale-alert", {}),
)


def _coinglass_wallet_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        rows = data.get("list")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def _coinglass_wallet_addresses(rows: list[dict[str, Any]]) -> list[str]:
    addresses: set[str] = set()
    for row in rows:
        address = row.get("user") or row.get("address") or row.get("user_address")
        if isinstance(address, str) and address.strip():
            addresses.add(address.strip().lower())
    return sorted(addresses)


def _latest_coinglass_wallet_event_time(rows: list[dict[str, Any]]) -> int | None:
    latest_ms = 0
    for row in rows:
        for key in ("create_time", "update_time"):
            try:
                latest_ms = max(latest_ms, int(row.get(key) or 0))
            except (TypeError, ValueError):
                continue
    return latest_ms or None


def _coinglass_server_key_payload() -> tuple[str, str | None]:
    from api.coinglass_routes import _mask_key, _server_coinglass_key

    api_key = _server_coinglass_key()
    return api_key, _mask_key(api_key) if api_key else None


def execute_analyze_tracked_address(db: Session, address: str) -> str:
    """Fetch CoinGlass Hyperliquid wallet position detail for Hyper AI analysis."""
    from fastapi import HTTPException
    from api.coinglass_routes import _coinglass_request

    normalized = (address or "").strip().lower()
    if not normalized:
        return json.dumps({"error": "address is required"})

    api_key, key_masked = _coinglass_server_key_payload()
    if not api_key:
        return json.dumps({
            "error": "CoinGlass API key is not configured for Hyper AI wallet analysis.",
            "next_steps": [
                "Save a CoinGlass key on the CoinGlass page or set COINGLASS_API_KEY on the server.",
                "After the key is configured, refresh Signals > Wallet Tracking and retry the wallet analysis."
            ]
        }, ensure_ascii=False)

    try:
        result = _coinglass_request(
            "/api/hyperliquid/user-position",
            {"user_address": normalized},
            api_key=api_key,
            key_source="server",
            key_masked=key_masked,
        )
    except HTTPException as exc:
        return json.dumps({
            "error": "Failed to fetch CoinGlass wallet position detail right now.",
            "detail": str(exc.detail),
            "next_steps": [
                "Confirm the CoinGlass key is valid and has access to Hyperliquid wallet endpoints.",
                "Retry after the CoinGlass request succeeds."
            ]
        }, ensure_ascii=False)

    if not result.get("ok"):
        return json.dumps({
            "error": "CoinGlass wallet position detail is unavailable right now.",
            "detail": result.get("msg") or (result.get("payload") or {}).get("message"),
            "next_steps": [
                "Confirm the address is a Hyperliquid wallet address.",
                "Confirm the CoinGlass plan supports the Hyperliquid wallet position endpoint."
            ]
        }, ensure_ascii=False)

    return json.dumps({
        "source": "coinglass",
        "address": normalized,
        "key_source": result.get("key_source"),
        "key_masked": result.get("key_masked"),
        "fetched_at": result.get("fetched_at"),
        "data": result.get("data"),
        "analysis_limit_note": (
            "CoinGlass returns current Hyperliquid wallet position and margin data for this address; "
            "it is not a complete all-time trading-history export."
        ),
    }, indent=2, ensure_ascii=False)


def execute_list_strategies(db: Session, strategy_id: int = None, strategy_type: str = None) -> str:
    """List all prompts and programs with binding status.
    Pass strategy_id + strategy_type to get full content of a specific strategy."""
    from database.models import (
        PromptTemplate, TradingProgram,
        AccountProgramBinding, AccountPromptBinding, Account
    )

    try:
        # Single strategy detail mode
        if strategy_id and strategy_type:
            if strategy_type == "prompt":
                tpl = db.query(PromptTemplate).filter(
                    PromptTemplate.id == strategy_id,
                    PromptTemplate.is_deleted == "false"
                ).first()
                if not tpl:
                    return json.dumps({"error": f"Prompt {strategy_id} not found"})
                bindings = db.query(AccountPromptBinding).filter(
                    AccountPromptBinding.prompt_template_id == tpl.id,
                    AccountPromptBinding.is_deleted != True
                ).all()
                bound_traders = []
                for b in bindings:
                    acc = db.get(Account, b.account_id)
                    if acc:
                        bound_traders.append({"trader_id": acc.id, "trader_name": acc.name})
                return json.dumps({
                    "prompt_id": tpl.id,
                    "name": tpl.name,
                    "description": getattr(tpl, "description", None),
                    "template_text": tpl.template_text,
                    "bound_traders": bound_traders
                }, indent=2)
            elif strategy_type == "program":
                prog = db.query(TradingProgram).filter(
                    TradingProgram.id == strategy_id,
                    TradingProgram.is_deleted != True
                ).first()
                if not prog:
                    return json.dumps({"error": f"Program {strategy_id} not found"})
                bindings = db.query(AccountProgramBinding).filter(
                    AccountProgramBinding.program_id == prog.id,
                    AccountProgramBinding.is_deleted != True
                ).all()
                bound_traders = []
                for b in bindings:
                    acc = db.get(Account, b.account_id)
                    if acc:
                        bound_traders.append({
                            "trader_id": acc.id, "trader_name": acc.name,
                            "is_active": b.is_active
                        })
                return json.dumps({
                    "program_id": prog.id,
                    "name": prog.name,
                    "description": prog.description,
                    "code": prog.code,
                    "bound_traders": bound_traders
                }, indent=2)

        # List all mode (original behavior)
        # Prompts
        templates = db.query(PromptTemplate).filter(
            PromptTemplate.is_deleted == "false"
        ).all()
        prompts = []
        for tpl in templates:
            bindings = db.query(AccountPromptBinding).filter(
                AccountPromptBinding.prompt_template_id == tpl.id,
                AccountPromptBinding.is_deleted != True
            ).all()
            bound_traders = []
            for b in bindings:
                acc = db.get(Account, b.account_id)
                if acc:
                    bound_traders.append({"trader_id": acc.id, "trader_name": acc.name})
            prompts.append({
                "prompt_id": tpl.id,
                "name": tpl.name,
                "description": getattr(tpl, "description", None),
                "bound_traders": bound_traders
            })

        # Programs
        programs_db = db.query(TradingProgram).filter(TradingProgram.is_deleted != True).all()
        programs = []
        for prog in programs_db:
            bindings = db.query(AccountProgramBinding).filter(
                AccountProgramBinding.program_id == prog.id,
                AccountProgramBinding.is_deleted != True
            ).all()
            bound_traders = []
            for b in bindings:
                acc = db.get(Account, b.account_id)
                if acc:
                    bound_traders.append({
                        "trader_id": acc.id,
                        "trader_name": acc.name,
                        "is_active": b.is_active
                    })
            programs.append({
                "program_id": prog.id,
                "name": prog.name,
                "description": prog.description,
                "bound_traders": bound_traders
            })

        return json.dumps({
            "prompts": prompts,
            "programs": programs,
            "prompt_count": len(prompts),
            "program_count": len(programs)
        }, indent=2)

    except Exception as e:
        logger.error(f"[list_strategies] Error: {e}")
        return json.dumps({"error": str(e)})

def execute_get_tracked_wallets(db: Session) -> str:
    """Return the current CoinGlass wallet tracking state and available wallet addresses."""
    from fastapi import HTTPException
    from api.coinglass_routes import _coinglass_request

    api_key, key_masked = _coinglass_server_key_payload()
    if not api_key:
        return json.dumps({
            "connected": False,
            "status": "not_configured",
            "source": "coinglass",
            "tracked_wallet_count": 0,
            "tracked_wallets": [],
            "last_event_at": None,
            "last_error": "CoinGlass API key is not configured for Hyper AI wallet tracking tools.",
            "usage_note": (
                "Signal System uses CoinGlass wallet tracking. Hyper AI can summarize it when a server "
                "CoinGlass key is available, or the user can inspect the Signal System wallet page with "
                "their own configured CoinGlass key."
            ),
        }, indent=2, ensure_ascii=False)

    addresses: set[str] = set()
    source_statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    latest_event_ms: int | None = None

    for source_id, path, params in COINGLASS_WALLET_TRACKING_ENDPOINTS:
        try:
            result = _coinglass_request(
                path,
                params,
                api_key=api_key,
                key_source="server",
                key_masked=key_masked,
            )
        except HTTPException as exc:
            detail = str(exc.detail)
            errors.append(f"{source_id}: {detail}")
            source_statuses.append({"id": source_id, "path": path, "ok": False, "message": detail})
            continue

        rows = _coinglass_wallet_rows(result.get("data"))
        addresses.update(_coinglass_wallet_addresses(rows))
        event_ms = _latest_coinglass_wallet_event_time(rows)
        if event_ms is not None:
            latest_event_ms = max(latest_event_ms or 0, event_ms)
        source_statuses.append({
            "id": source_id,
            "path": path,
            "ok": bool(result.get("ok")),
            "message": result.get("msg"),
            "row_count": len(rows),
        })
        if not result.get("ok"):
            errors.append(f"{source_id}: {result.get('msg') or 'CoinGlass request failed'}")

    synced_addresses = sorted(addresses)
    connected = any(item.get("ok") for item in source_statuses)
    last_event_at = (
        datetime.fromtimestamp(latest_event_ms / 1000, tz=timezone.utc).replace(tzinfo=None).isoformat()
        if latest_event_ms else None
    )
    result = {
        "connected": connected,
        "status": "connected" if connected else "error",
        "source": "coinglass",
        "key_source": "server",
        "key_masked": key_masked,
        "tracked_wallet_count": len(synced_addresses),
        "tracked_wallets": synced_addresses,
        "last_connected_at": datetime.utcnow().isoformat() if connected else None,
        "last_event_at": last_event_at,
        "last_error": "; ".join(errors) if errors and not connected else None,
        "data_sources": source_statuses,
        "usage_note": (
            "This list reflects wallet addresses currently available from CoinGlass Hyperliquid "
            "whale position and whale alert endpoints. It is the CoinGlass-backed source for "
            "CEC-codex wallet-tracking signal pools."
        ),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


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




# =============================================================================
# Tool dispatch
# =============================================================================
from services.hyper_ai_tools_dispatch import execute_hyper_ai_tool
