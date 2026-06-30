import hashlib
import json
from datetime import datetime
from typing import Optional

from dateutil.parser import parse
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models import (
    Account,
    AccountPromptBinding,
    AccountStrategyConfig,
    AIDecisionLog,
    SignalTriggerLog,
)
from database.snapshot_models import HyperliquidTrade

from .export_service import EXPORT_VERSION


def generate_dedup_key(decision_time: str, symbol: str, decision_snapshot: str) -> str:
    """Generate a unique key for deduplication."""
    content = f"{decision_time}|{symbol or ''}|{decision_snapshot or ''}"
    return hashlib.md5(content.encode()).hexdigest()


def find_duplicate_log(db: Session, account_id: int, log_data: dict) -> bool:
    """Check if a similar decision log already exists."""
    decision_time_str = log_data.get("decision_time") or log_data.get("created_at")
    if not decision_time_str:
        return False

    try:
        decision_time = parse(decision_time_str)
        if decision_time.tzinfo:
            decision_time = decision_time.replace(tzinfo=None)
    except Exception:
        return False

    symbol = log_data.get("symbol")
    decision_snapshot = log_data.get("decision_snapshot")

    query = db.query(AIDecisionLog).filter(
        AIDecisionLog.account_id == account_id,
        AIDecisionLog.decision_time == decision_time,
    )

    if symbol:
        query = query.filter(AIDecisionLog.symbol == symbol)

    existing = query.first()
    if existing and existing.decision_snapshot == decision_snapshot:
        return True

    return False


def find_duplicate_trade(snapshot_db: Session, order_id: str, trade_time: datetime) -> bool:
    """Check if a trade with same order_id and trade_time already exists."""
    existing = snapshot_db.query(HyperliquidTrade).filter(
        HyperliquidTrade.order_id == order_id,
        HyperliquidTrade.trade_time == trade_time,
    ).first()
    return existing is not None


def preview_import_data(account_id: int, data: dict, db: Session) -> dict:
    """
    Preview import: analyze the data and return what will be imported/skipped.
    Also check if target account has prompt/signal bindings.
    """
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.is_deleted != True,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if data.get("version") != EXPORT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export version: {data.get('version')}",
        )

    decision_logs = data.get("decision_logs", [])

    will_import = []
    will_skip = []

    for log in decision_logs:
        if find_duplicate_log(db, account_id, log):
            will_skip.append({
                "decision_time": log.get("decision_time"),
                "symbol": log.get("symbol"),
                "operation": log.get("operation"),
                "reason": "Duplicate record exists",
            })
        else:
            will_import.append(log)

    warnings = []
    prompt_binding = db.query(AccountPromptBinding).filter(
        AccountPromptBinding.account_id == account_id,
        AccountPromptBinding.is_deleted != True,
    ).first()

    strategy_config = db.query(AccountStrategyConfig).filter(
        AccountStrategyConfig.account_id == account_id,
    ).first()

    if not prompt_binding:
        warnings.append("Target AI Trader has no prompt template binding")
    if not strategy_config or not strategy_config.signal_pool_ids:
        warnings.append("Target AI Trader has no signal pool binding")

    total_trades = sum(len(log.get("trades", [])) for log in will_import)

    return {
        "will_import": {
            "decision_logs": len(will_import),
            "trades": total_trades,
        },
        "will_skip": {
            "count": len(will_skip),
            "details": will_skip[:10],
        },
        "warnings": warnings,
        "target_account": {
            "id": account.id,
            "name": account.name,
            "has_prompt_binding": prompt_binding is not None,
            "has_signal_binding": strategy_config is not None and bool(strategy_config.signal_pool_ids),
        },
    }


def execute_import_data(
    account_id: int,
    data,
    confirmed: bool,
    db: Session,
    snapshot_db: Session,
) -> dict:
    """Execute the import: create decision logs and trades in both databases."""
    if not confirmed:
        raise HTTPException(status_code=400, detail="Import must be confirmed")

    account = db.query(Account).filter(
        Account.id == account_id,
        Account.is_deleted != True,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Target account not found")

    prompt_binding = db.query(AccountPromptBinding).filter(
        AccountPromptBinding.account_id == account_id,
        AccountPromptBinding.is_deleted != True,
    ).first()
    target_prompt_template_id = prompt_binding.prompt_template_id if prompt_binding else None

    target_signal_trigger_id = None
    strategy_config = db.query(AccountStrategyConfig).filter(
        AccountStrategyConfig.account_id == account_id,
    ).first()
    if strategy_config and strategy_config.signal_pool_ids:
        try:
            pool_ids = json.loads(strategy_config.signal_pool_ids)
            if pool_ids and len(pool_ids) > 0:
                first_pool_id = pool_ids[0]
                trigger_record = db.query(SignalTriggerLog).filter(
                    SignalTriggerLog.pool_id == first_pool_id,
                ).first()
                if trigger_record:
                    target_signal_trigger_id = trigger_record.id
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        import_data = json.loads(data) if isinstance(data, str) else data
        decision_logs = import_data.get("decision_logs", [])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")

    imported_logs = 0
    imported_trades = 0
    skipped_logs = 0
    skipped_trades = 0
    errors = []

    try:
        for log_data in decision_logs:
            _decision_time = parse(log_data["decision_time"])
            symbol = log_data["symbol"]
            decision_snapshot = log_data.get("decision_snapshot")

            if find_duplicate_log(db, account_id, {
                "decision_time": log_data["decision_time"],
                "symbol": symbol,
                "decision_snapshot": decision_snapshot,
            }):
                skipped_logs += 1
                skipped_trades += len(log_data.get("trades", []))
                continue

            try:
                import_decision_log(
                    db,
                    account_id,
                    log_data,
                    target_prompt_template_id,
                    target_signal_trigger_id,
                )
                imported_logs += 1

                for trade_data in log_data.get("trades", []):
                    try:
                        trade_time = parse(trade_data["trade_time"])
                        if find_duplicate_trade(snapshot_db, trade_data["order_id"], trade_time):
                            skipped_trades += 1
                            continue

                        import_trade(snapshot_db, account_id, trade_data)
                        imported_trades += 1
                    except Exception as e:
                        errors.append(f"Trade import error (order_id={trade_data.get('order_id')}): {str(e)}")
                        skipped_trades += 1

            except Exception as e:
                errors.append(f"Decision log import error (symbol={symbol}, time={log_data['decision_time']}): {str(e)}")
                skipped_logs += 1
                skipped_trades += len(log_data.get("trades", []))

        db.commit()
        snapshot_db.commit()

    except Exception as e:
        db.rollback()
        snapshot_db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

    return {
        "success": True,
        "imported": {
            "decision_logs": imported_logs,
            "trades": imported_trades,
        },
        "skipped": {
            "decision_logs": skipped_logs,
            "trades": skipped_trades,
        },
        "errors": errors[:10] if errors else [],
    }


def import_decision_log(
    db: Session,
    account_id: int,
    log_data: dict,
    target_prompt_template_id: Optional[int] = None,
    target_signal_trigger_id: Optional[int] = None,
) -> AIDecisionLog:
    """Import a single decision log into the main database."""
    decision_time = parse(log_data["decision_time"])
    pnl_updated_at = parse(log_data["pnl_updated_at"]) if log_data.get("pnl_updated_at") else None

    new_log = AIDecisionLog(
        account_id=account_id,
        symbol=log_data.get("symbol"),
        decision_time=decision_time,
        operation=log_data["operation"],
        reason=log_data.get("reason"),
        prev_portion=log_data.get("prev_portion", 0),
        target_portion=log_data.get("target_portion", 0),
        total_balance=log_data.get("total_balance", 0),
        executed=log_data.get("executed", "false"),
        prompt_snapshot=log_data.get("prompt_snapshot"),
        reasoning_snapshot=log_data.get("reasoning_snapshot"),
        decision_snapshot=log_data.get("decision_snapshot"),
        hyperliquid_environment=log_data.get("hyperliquid_environment"),
        wallet_address=log_data.get("wallet_address"),
        hyperliquid_order_id=log_data.get("hyperliquid_order_id"),
        tp_order_id=log_data.get("tp_order_id"),
        sl_order_id=log_data.get("sl_order_id"),
        realized_pnl=log_data.get("realized_pnl"),
        pnl_updated_at=pnl_updated_at,
        signal_trigger_id=target_signal_trigger_id,
        prompt_template_id=target_prompt_template_id,
    )
    db.add(new_log)
    db.flush()
    return new_log


def import_trade(snapshot_db: Session, account_id: int, trade_data: dict) -> HyperliquidTrade:
    """Import a single trade into the snapshot database."""
    new_trade = HyperliquidTrade(
        account_id=account_id,
        environment=trade_data.get("environment", "mainnet"),
        wallet_address=trade_data.get("wallet_address"),
        symbol=trade_data["symbol"],
        side=trade_data["side"],
        quantity=trade_data["quantity"],
        price=trade_data["price"],
        leverage=trade_data.get("leverage", 1),
        order_id=trade_data["order_id"],
        order_status="filled",
        trade_value=trade_data["trade_value"],
        fee=trade_data.get("fee", 0),
        trade_time=parse(trade_data["trade_time"]),
    )
    snapshot_db.add(new_trade)
    snapshot_db.flush()
    return new_trade
