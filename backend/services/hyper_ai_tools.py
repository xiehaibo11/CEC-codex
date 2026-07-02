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
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text, func

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
    from services.hyper_ai_strategy_tools import execute_list_strategies as _execute_list_strategies

    return _execute_list_strategies(db, strategy_id=strategy_id, strategy_type=strategy_type)

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


_STRATEGY_RADAR_UNIVERSE_CACHE: dict[str, Any] = {"moved_to": "hyper_ai_strategy_radar"}


def execute_get_strategy_radar_universe(db: Session) -> str:
    """Return Strategy Radar's currently queryable symbol/period/regime combinations."""
    from services.hyper_ai_strategy_radar import execute_get_strategy_radar_universe as _execute

    return _execute(db)


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
    from services.hyper_ai_strategy_radar import execute_search_strategy_radar as _execute

    return _execute(
        db,
        symbol=symbol,
        period=period,
        regime=regime,
        exchange=exchange,
        strategy_type=strategy_type,
        sort_by=sort_by,
        risk_level=risk_level,
        timeframe=timeframe,
        limit=limit,
    )




# =============================================================================
# Tool dispatch
# =============================================================================
from services.hyper_ai_tools_dispatch import execute_hyper_ai_tool
