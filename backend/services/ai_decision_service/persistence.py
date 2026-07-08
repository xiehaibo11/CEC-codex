"""AI decision persistence and active-account selection.

_is_default_api_key gate, save_ai_decision (AIDecisionLog write), and
get_active_ai_accounts query.
"""
import json
import logging
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import Account, AIDecisionLog
from repositories.strategy_repo import set_last_trigger
from services.system_logger import system_logger

from services.ai_decision_service.constants import DEMO_API_KEYS

logger = logging.getLogger(__name__)


def _is_default_api_key(api_key: str) -> bool:
    """Check if the API key is a default/placeholder key that should be skipped"""
    return api_key in DEMO_API_KEYS
def save_ai_decision(
    db: Session,
    account: Account,
    decision: Dict,
    portfolio: Dict,
    executed: bool = False,
    order_id: Optional[int] = None,
    wallet_address: Optional[str] = None,
    # Decision tracking fields for analysis chain
    prompt_template_id: Optional[int] = None,
    signal_trigger_id: Optional[int] = None,
    hyperliquid_order_id: Optional[str] = None,
    tp_order_id: Optional[str] = None,
    sl_order_id: Optional[str] = None,
    # Exchange identifier for attribution analysis
    exchange: Optional[str] = None,
) -> None:
    """Save AI decision to the decision log"""
    try:
        operation = decision.get("operation", "").lower() if decision.get("operation") else ""
        symbol_raw = decision.get("symbol")
        symbol = symbol_raw.upper() if symbol_raw else None
        target_portion = float(decision.get("target_portion_of_balance", 0)) if decision.get("target_portion_of_balance") is not None else 0.0
        reason = decision.get("reason", "No reason provided")
        prompt_snapshot = decision.get("_prompt_snapshot")
        reasoning_snapshot = decision.get("_reasoning_snapshot")
        raw_decision_snapshot = decision.get("_raw_decision_text")
        decision_snapshot_structured = None
        try:
            decision_payload = {k: v for k, v in decision.items() if not k.startswith("_")}
            decision_snapshot_structured = json.dumps(decision_payload, indent=2, ensure_ascii=False)
        except Exception:
            decision_snapshot_structured = raw_decision_snapshot

        if (not reasoning_snapshot or not reasoning_snapshot.strip()) and isinstance(raw_decision_snapshot, str):
            candidate = raw_decision_snapshot.strip()
            extracted_reasoning: Optional[str] = None
            if candidate:
                # Try to strip JSON payload to keep narrative reasoning only
                json_start = candidate.find('{')
                json_end = candidate.rfind('}')
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    prefix = candidate[:json_start].strip()
                    suffix = candidate[json_end + 1 :].strip()
                    parts = [part for part in (prefix, suffix) if part]
                    if parts:
                        extracted_reasoning = '\n\n'.join(parts)
                else:
                    extracted_reasoning = candidate if not candidate.startswith('{') else None

            if extracted_reasoning:
                reasoning_snapshot = extracted_reasoning

        # Calculate previous portion for the symbol
        prev_portion = 0.0
        if operation in ["sell", "hold"] and symbol:
            positions = portfolio.get("positions", {})
            if symbol in positions:
                symbol_value = positions[symbol]["current_value"]
                total_balance = portfolio["total_assets"]
                if total_balance > 0:
                    prev_portion = symbol_value / total_balance

        # Get Hyperliquid environment for decision tagging
        # IMPORTANT: Always use global trading mode for accurate logging
        from services.hyperliquid_environment import get_global_trading_mode
        hyperliquid_environment = get_global_trading_mode(db)

        # Create decision log entry
        decision_log = AIDecisionLog(
            account_id=account.id,
            reason=reason,
            operation=operation,
            symbol=symbol,
            prev_portion=Decimal(str(prev_portion)),
            target_portion=Decimal(str(target_portion)),
            total_balance=Decimal(str(portfolio["total_assets"])),
            executed="true" if executed else "false",
            order_id=order_id,
            prompt_snapshot=prompt_snapshot,
            reasoning_snapshot=reasoning_snapshot,
            decision_snapshot=decision_snapshot_structured or raw_decision_snapshot,
            hyperliquid_environment=hyperliquid_environment,
            wallet_address=wallet_address,
            # Decision tracking fields for analysis chain
            prompt_template_id=prompt_template_id,
            signal_trigger_id=signal_trigger_id,
            hyperliquid_order_id=hyperliquid_order_id,
            tp_order_id=tp_order_id,
            sl_order_id=sl_order_id,
            # Exchange identifier (NULL treated as "hyperliquid" for backward compatibility)
            exchange=exchange,
            review_run_id=decision.get("review_run_id"),
            review_verdict=decision.get("review_verdict"),
            review_blocked_reason=decision.get("review_blocked_reason"),
        )

        db.add(decision_log)
        db.commit()
        db.refresh(decision_log)

        if decision_log.decision_time:
            set_last_trigger(db, account.id, decision_log.decision_time)

        symbol_str = symbol if symbol else "N/A"
        logger.info(f"Saved AI decision log for account {account.name}: {operation} {symbol_str} "
                   f"prev_portion={prev_portion:.4f} target_portion={target_portion:.4f} executed={executed}")

        # Log to system logger
        system_logger.log_ai_decision(
            account_name=account.name,
            model=account.model,
            operation=operation,
            symbol=symbol,
            reason=reason,
            success=executed
        )

        # Broadcast AI decision update via WebSocket
        import asyncio
        from api.ws import broadcast_model_chat_update

        try:
            broadcast_data = {
                "id": decision_log.id,
                "account_id": account.id,
                "account_name": account.name,
                "model": account.model,
                "decision_time": decision_log.decision_time.isoformat() if hasattr(decision_log.decision_time, 'isoformat') else str(decision_log.decision_time),
                "operation": decision_log.operation.upper() if decision_log.operation else "HOLD",
                "symbol": decision_log.symbol,
                "reason": decision_log.reason,
                "prev_portion": float(decision_log.prev_portion),
                "target_portion": float(decision_log.target_portion),
                "total_balance": float(decision_log.total_balance),
                "executed": decision_log.executed == "true",
                "order_id": decision_log.order_id,
                "prompt_snapshot": decision_log.prompt_snapshot,
                "reasoning_snapshot": decision_log.reasoning_snapshot,
                "decision_snapshot": decision_log.decision_snapshot,
                "wallet_address": decision_log.wallet_address,
            }
            
            # Check if there's a running event loop
            try:
                loop = asyncio.get_running_loop()
                # Event loop is running, create task
                loop.create_task(broadcast_model_chat_update(broadcast_data))
            except RuntimeError:
                # No running event loop, run synchronously
                asyncio.run(broadcast_model_chat_update(broadcast_data))
        except Exception as broadcast_err:
            # Don't fail the save operation if broadcast fails
            logger.warning(f"Failed to broadcast AI decision update: {broadcast_err}")

        # Bot push notification for AI Trader decisions
        try:
            from api.bot_routes import get_notification_config_dict
            from services.bot_event_service import enqueue_system_event, push_event_to_all_channels
            notif_config = get_notification_config_dict(db)
            if notif_config.get("ai_trader", True) and executed and operation and operation.lower() != "hold":
                event_data = {
                    "trader_name": account.name,
                    "operation": operation.upper() if operation else "HOLD",
                    "symbol": symbol or "N/A",
                    "target_portion": f"{target_portion:.1%}" if target_portion else "0%",
                    "price": "market",
                    "reason": reason[:100] if reason else "",
                }
                results = enqueue_system_event(db, "ai_decision", event_data)
                if results:
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(push_event_to_all_channels(db, results))
                    except RuntimeError:
                        asyncio.run(push_event_to_all_channels(db, results))
        except Exception as notif_err:
            logger.warning(f"Failed to send bot notification: {notif_err}")

    except Exception as err:
        logger.error(f"Failed to save AI decision log: {err}")
        db.rollback()


def get_active_ai_accounts(db: Session) -> List[Account]:
    """Get all active AI accounts that are not using default API key"""
    accounts = db.query(Account).filter(
        Account.is_active == "true",
        Account.account_type == "AI",
        Account.auto_trading_enabled == "true",
        Account.is_deleted != True
    ).all()
    
    if not accounts:
        return []
    
    # Filter out default accounts
    valid_accounts = [acc for acc in accounts if not _is_default_api_key(acc.api_key)]
    
    if not valid_accounts:
        logger.debug("No valid AI accounts found (all using default keys)")
        return []
        
    return valid_accounts
