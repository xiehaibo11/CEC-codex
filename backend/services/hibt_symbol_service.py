"""HiBT symbol management utilities.

Handles:
- Fetching tradable symbol metadata from HiBT perpetual futures API
- Persisting available symbols + user-selected watchlist in SystemConfig
- Exposing helpers for manual trading and future collectors.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import SystemConfig
from services.hibt_trading_client import HibtTradingClient

logger = logging.getLogger(__name__)

HIBT_AVAILABLE_SYMBOLS_KEY = "hibt_available_symbols"
HIBT_SELECTED_SYMBOLS_KEY = "hibt_selected_symbols"
MAX_WATCHLIST_SYMBOLS = 10
SYMBOL_REFRESH_TASK_ID = "hibt_symbol_refresh"

DEFAULT_SYMBOLS: List[Dict[str, str]] = [
    {"symbol": "BTC", "name": "Bitcoin", "type": "perpetual"},
]


def _load_config_value(db: Session, key: str) -> Optional[str]:
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return config.value if config else None


def _save_config_value(db: Session, key: str, value: str) -> None:
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        config = SystemConfig(key=key, value=value)
        db.add(config)
    else:
        config.value = value
    db.commit()


def _parse_symbol_json(value: Optional[str]) -> List[Dict[str, str]]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            return []
        result: List[Dict[str, str]] = []
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol") or "").upper()
            if not symbol:
                continue
            result.append(
                {
                    "symbol": symbol,
                    "name": str(entry.get("name") or symbol),
                    "type": str(entry.get("type") or "perpetual"),
                }
            )
        return result
    except json.JSONDecodeError:
        logger.warning("[HiBT] Failed to decode stored symbols; falling back to defaults")
    return []


def _serialize_symbols(symbols: List[Dict[str, str]]) -> str:
    sanitized: List[Dict[str, str]] = []
    seen: set[str] = set()
    for entry in symbols:
        symbol = str(entry.get("symbol") or "").upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        sanitized.append(
            {
                "symbol": symbol,
                "name": str(entry.get("name") or symbol),
                "type": str(entry.get("type") or "perpetual"),
            }
        )
    return json.dumps(sanitized)


def _display_symbol(raw_symbol: str) -> str:
    symbol = str(raw_symbol or "").strip().upper().replace("-", "_").replace("/", "_")
    if not symbol:
        return ""
    if "_" in symbol:
        return symbol.split("_", 1)[0]
    if symbol.endswith("USDT"):
        return symbol[:-4]
    return symbol


def _is_tradable(entry: Dict) -> bool:
    """Best-effort support for HiBT's symbol metadata variants."""
    for key in ("supportTrade", "support_trading", "enableTrade", "trade"):
        if key in entry:
            value = entry.get(key)
            return value is True or str(value).lower() in {"true", "1", "yes"}
    status = str(entry.get("status") or entry.get("state") or "").lower()
    if status:
        return status in {"online", "trading", "1", "open"}
    return True


def fetch_remote_symbols() -> List[Dict[str, str]]:
    """Fetch tradable symbols from HiBT perpetual futures API."""
    try:
        client = HibtTradingClient(access_key="", secret_key="")
        symbols_data = client.get_symbols()
    except Exception as err:
        logger.warning("[HiBT] Failed to fetch symbol catalog: %s", err)
        return []

    results: List[Dict[str, str]] = []
    seen: set[str] = set()

    for entry in symbols_data:
        if not isinstance(entry, dict):
            continue
        raw_symbol = str(entry.get("symbol") or entry.get("contractName") or "")
        base_asset = _display_symbol(raw_symbol)
        if not base_asset or base_asset in seen:
            continue
        if not _is_tradable(entry):
            continue

        seen.add(base_asset)
        results.append(
            {
                "symbol": base_asset,
                "name": str(entry.get("base") or entry.get("baseCurrency") or base_asset).upper(),
                "type": "perpetual",
            }
        )

    logger.info("[HiBT] Fetched %d tradable symbols from Futures API", len(results))
    return results


def refresh_hibt_symbols() -> List[Dict[str, str]]:
    """Refresh available HiBT symbol list."""
    remote_symbols = fetch_remote_symbols()
    if not remote_symbols:
        logger.warning("[HiBT] No symbols fetched from API; keeping existing list")

    with SessionLocal() as db:
        if remote_symbols:
            _save_config_value(db, HIBT_AVAILABLE_SYMBOLS_KEY, _serialize_symbols(remote_symbols))
            _ensure_watchlist_valid(db, remote_symbols)
            logger.info("[HiBT] Symbol catalog refreshed (%d symbols)", len(remote_symbols))
        else:
            stored = _parse_symbol_json(_load_config_value(db, HIBT_AVAILABLE_SYMBOLS_KEY))
            if not stored:
                _save_config_value(db, HIBT_AVAILABLE_SYMBOLS_KEY, _serialize_symbols(DEFAULT_SYMBOLS))
                _ensure_watchlist_valid(db, DEFAULT_SYMBOLS)
    return get_available_symbols()


def _ensure_watchlist_valid(db: Session, available: List[Dict[str, str]]) -> None:
    available_set = {item["symbol"] for item in available}
    raw_value = _load_config_value(db, HIBT_SELECTED_SYMBOLS_KEY)

    if not raw_value:
        for seed_key in ("binance_selected_symbols", "hyperliquid_selected_symbols"):
            seed_value = _load_config_value(db, seed_key)
            if not seed_value:
                continue
            try:
                seed_symbols = json.loads(seed_value)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(seed_symbols, list):
                valid_symbols = [str(s).upper() for s in seed_symbols if str(s).upper() in available_set][:MAX_WATCHLIST_SYMBOLS]
                if valid_symbols:
                    _save_config_value(db, HIBT_SELECTED_SYMBOLS_KEY, json.dumps(valid_symbols))
                    logger.info("[HiBT] Initialized watchlist from %s: %s", seed_key, valid_symbols)
                    return

        default = [entry["symbol"] for entry in DEFAULT_SYMBOLS if entry["symbol"] in available_set]
        if not default:
            default = [entry["symbol"] for entry in available[:3]]
        _save_config_value(db, HIBT_SELECTED_SYMBOLS_KEY, json.dumps(default))
        logger.info("[HiBT] Initialized watchlist with defaults: %s", default)
        return

    try:
        symbols = json.loads(raw_value)
        if not isinstance(symbols, list):
            raise ValueError("Selection is not a list")
    except Exception:
        logger.warning("[HiBT] Invalid watchlist stored; resetting to defaults")
        default = [entry["symbol"] for entry in DEFAULT_SYMBOLS if entry["symbol"] in available_set]
        if not default:
            default = [entry["symbol"] for entry in available[:3]]
        _save_config_value(db, HIBT_SELECTED_SYMBOLS_KEY, json.dumps(default))
        return

    filtered = [str(s).upper() for s in symbols if str(s).upper() in available_set]
    if len(filtered) != len(symbols):
        removed = set(map(str, symbols)) - set(filtered)
        logger.warning("[HiBT] Removed invalid symbols from watchlist: %s", removed)
        _save_config_value(db, HIBT_SELECTED_SYMBOLS_KEY, json.dumps(filtered[:MAX_WATCHLIST_SYMBOLS]))


def get_available_symbols() -> List[Dict[str, str]]:
    """Return cached available symbols."""
    with SessionLocal() as db:
        symbols = _parse_symbol_json(_load_config_value(db, HIBT_AVAILABLE_SYMBOLS_KEY))
        if not symbols:
            return DEFAULT_SYMBOLS.copy()
        return symbols


def get_available_symbols_info() -> Dict:
    """Return available symbols with metadata for API response."""
    symbols = get_available_symbols()
    return {
        "symbols": symbols,
        "count": len(symbols),
    }


def get_selected_symbols() -> List[str]:
    """Return currently selected HiBT watchlist symbols."""
    with SessionLocal() as db:
        raw_value = _load_config_value(db, HIBT_SELECTED_SYMBOLS_KEY)
        if not raw_value:
            available = get_available_symbols()
            _ensure_watchlist_valid(db, available)
            raw_value = _load_config_value(db, HIBT_SELECTED_SYMBOLS_KEY)
            if not raw_value:
                default = [entry["symbol"] for entry in DEFAULT_SYMBOLS]
                _save_config_value(db, HIBT_SELECTED_SYMBOLS_KEY, json.dumps(default))
                return default

        try:
            symbols = json.loads(raw_value)
            if isinstance(symbols, list):
                return [str(symbol).upper() for symbol in symbols]
        except json.JSONDecodeError:
            logger.warning("[HiBT] Failed to parse watchlist; returning defaults")

        default = [entry["symbol"] for entry in DEFAULT_SYMBOLS]
        _save_config_value(db, HIBT_SELECTED_SYMBOLS_KEY, json.dumps(default))
        return default


def update_selected_symbols(symbols: List[str]) -> List[str]:
    """Persist new HiBT watchlist (validated)."""
    available = get_available_symbols()
    available_set = {item["symbol"] for item in available}

    unique_symbols: List[str] = []
    seen: set[str] = set()
    for sym in symbols:
        sym_upper = str(sym).upper()
        if sym_upper in seen:
            continue
        if sym_upper not in available_set:
            logger.warning("[HiBT] Symbol '%s' not in available list, skipping", sym_upper)
            continue
        seen.add(sym_upper)
        unique_symbols.append(sym_upper)

    if len(unique_symbols) > MAX_WATCHLIST_SYMBOLS:
        logger.warning("[HiBT] Watchlist exceeds max %d symbols, truncating", MAX_WATCHLIST_SYMBOLS)
        unique_symbols = unique_symbols[:MAX_WATCHLIST_SYMBOLS]

    with SessionLocal() as db:
        _save_config_value(db, HIBT_SELECTED_SYMBOLS_KEY, json.dumps(unique_symbols))

    logger.info("[HiBT] Watchlist updated: %s", ", ".join(unique_symbols) or "none")
    return unique_symbols


def get_symbol_map() -> Dict[str, Dict[str, str]]:
    """Return a map of symbol -> metadata."""
    symbols = get_available_symbols()
    return {item["symbol"]: item for item in symbols}


def schedule_symbol_refresh_task(interval_seconds: int = 7200) -> None:
    """Register periodic HiBT symbol refresh job."""
    from services.scheduler import task_scheduler

    def _task():
        try:
            refreshed = refresh_hibt_symbols()
            logger.debug("[HiBT] Symbol refresh task ran; %d symbols available", len(refreshed))
        except Exception as err:
            logger.warning("[HiBT] Symbol refresh failed: %s", err)

    task_scheduler.remove_task(SYMBOL_REFRESH_TASK_ID)
    task_scheduler.add_interval_task(
        task_func=_task,
        interval_seconds=interval_seconds,
        task_id=SYMBOL_REFRESH_TASK_ID,
    )
    logger.info("[HiBT] Symbol refresh task scheduled (interval: %ds)", interval_seconds)
