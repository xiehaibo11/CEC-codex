"""Hard time-based exit for AI-managed Binance positions.

用户规则（2026-07-10）：5分钟一到就平仓。The LLM decision cycle runs on a
multi-minute cadence and holds through it; this deterministic 30-second
scheduler job enforces the fixed holding horizon instead:

- every cycle, each auto-trading Binance account's open positions are read
  with timing (opened_at derived from user fills);
- any position held >= ``POSITION_MAX_HOLD_MINUTES`` (default 5) is closed at
  market with TP/SL cleanup, and a ``close`` decision row is logged for
  attribution ("时间退出" reason);
- positions whose age cannot be established are SKIPPED with a warning —
  closing blind could kill a position opened seconds ago.

Env knobs: ``POSITION_TIME_EXIT_ENABLED`` (default "true"),
``POSITION_MAX_HOLD_MINUTES`` (default 5).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

DEFAULT_MAX_HOLD_MINUTES = 5

TIME_EXIT_JOB_ID = "position_time_exit_cycle"


def _enabled() -> bool:
    return os.getenv("POSITION_TIME_EXIT_ENABLED", "true").strip().lower() != "false"


def _max_hold_seconds() -> int:
    try:
        minutes = float(os.getenv("POSITION_MAX_HOLD_MINUTES", DEFAULT_MAX_HOLD_MINUTES))
    except ValueError:
        minutes = DEFAULT_MAX_HOLD_MINUTES
    return int(minutes * 60)


def positions_due_for_exit(
    positions: List[Dict[str, Any]], max_hold_seconds: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split open positions into (due-for-close, unknown-age-skipped)."""
    due: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for pos in positions or []:
        if not float(pos.get("szi") or 0):
            continue
        held = pos.get("holding_duration_seconds")
        if held is None:
            skipped.append(pos)
        elif float(held) >= max_hold_seconds:
            due.append(pos)
    return due, skipped


def close_due_positions(
    client: Any,
    positions: List[Dict[str, Any]],
    max_hold_seconds: int,
) -> List[Dict[str, Any]]:
    """Close every due position (TP/SL cleaned up); one venue failure never
    stops the rest. Returns one result row per due position."""
    due, skipped = positions_due_for_exit(positions, max_hold_seconds)
    for pos in skipped:
        logger.warning(
            "[TimeExit] %s position age unknown (fills lookup failed?) - NOT closing blind",
            pos.get("coin"),
        )
    results: List[Dict[str, Any]] = []
    for pos in due:
        symbol = str(pos.get("coin") or "")
        try:
            order = client.close_position(symbol, cancel_tpsl=True)
            results.append(
                {
                    "symbol": symbol,
                    "closed": True,
                    "order_id": (order or {}).get("order_id"),
                    "held_seconds": pos.get("holding_duration_seconds"),
                }
            )
            logger.info(
                "[TimeExit] closed %s after %.0fs (limit %ss)",
                symbol, float(pos.get("holding_duration_seconds") or 0), max_hold_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - per-position isolation
            logger.error("[TimeExit] failed to close %s: %s", symbol, exc)
            results.append({"symbol": symbol, "closed": False, "error": str(exc)})
    return results


def run_position_time_exit_cycle() -> Dict[str, int]:
    """One scheduler cycle over all auto-trading Binance accounts."""
    counters = {"accounts": 0, "closed": 0, "errors": 0, "skipped_unknown_age": 0}
    if not _enabled():
        return counters

    from database.connection import SessionLocal
    from database.models import Account, BinanceWallet
    from services.binance_trading_client import BinanceTradingClient
    from services.hyperliquid_environment import get_global_trading_mode
    from utils.encryption import decrypt_private_key

    max_hold = _max_hold_seconds()
    db = SessionLocal()
    try:
        environment = get_global_trading_mode(db)
        if not environment:
            return counters
        accounts = (
            db.query(Account)
            .filter(
                Account.is_active == "true",
                Account.auto_trading_enabled == "true",
                Account.is_deleted != True,  # noqa: E712 - SQLAlchemy comparison
            )
            .all()
        )
        for account in accounts:
            wallet = (
                db.query(BinanceWallet)
                .filter(
                    BinanceWallet.account_id == account.id,
                    BinanceWallet.environment == environment,
                    BinanceWallet.is_active == "true",
                )
                .first()
            )
            if not wallet or not wallet.api_key_encrypted:
                continue
            counters["accounts"] += 1
            try:
                client = BinanceTradingClient(
                    api_key=decrypt_private_key(wallet.api_key_encrypted),
                    secret_key=decrypt_private_key(wallet.secret_key_encrypted),
                    environment=wallet.environment or "testnet",
                )
                positions = client.get_positions(include_timing=True)
                due, skipped = positions_due_for_exit(positions, max_hold)
                counters["skipped_unknown_age"] += len(skipped)
                if not due:
                    for pos in skipped:
                        logger.warning(
                            "[TimeExit] %s position age unknown - NOT closing blind",
                            pos.get("coin"),
                        )
                    continue
                results = close_due_positions(client, positions, max_hold)
                for row in results:
                    if row["closed"]:
                        counters["closed"] += 1
                        _log_time_exit_decision(db, account, row, max_hold)
                    else:
                        counters["errors"] += 1
            except Exception as exc:  # noqa: BLE001 - per-account isolation
                counters["errors"] += 1
                logger.error(
                    "[TimeExit] cycle failed for account %s (%s): %s",
                    account.id, account.name, exc,
                )
    finally:
        db.close()
    return counters


def _log_time_exit_decision(
    db: Any, account: Any, result: Dict[str, Any], max_hold_seconds: int
) -> None:
    """Persist an attribution row so time exits show up in decision analytics."""
    try:
        from services.ai_decision_service import save_ai_decision

        decision = {
            "operation": "close",
            "symbol": result["symbol"],
            "target_portion_of_balance": 0,
            "reason": (
                f"时间退出规则：持有满 {max_hold_seconds // 60} 分钟强制平仓"
                f"（实际持有 {float(result.get('held_seconds') or 0):.0f} 秒）"
            ),
            "trading_strategy": "Deterministic time-based exit (fixed holding horizon).",
        }
        save_ai_decision(
            db, account, decision, {}, executed=True,
            hyperliquid_order_id=str(result.get("order_id")) if result.get("order_id") else None,
            exchange="binance",
        )
    except Exception as exc:  # noqa: BLE001 - logging must not undo the close
        logger.warning("[TimeExit] failed to log decision row: %s", exc)
