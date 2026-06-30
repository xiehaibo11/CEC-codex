from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.models import Account, AIDecisionLog
from database.snapshot_models import HyperliquidTrade

from .serialization import serialize_datetime


EXPORT_VERSION = "1.0"


def get_related_trades(
    snapshot_db: Session,
    hyperliquid_order_id: Optional[str],
    tp_order_id: Optional[str],
    sl_order_id: Optional[str],
) -> list[dict]:
    """Query HyperliquidTrade records for main/tp/sl orders and mark order_type."""
    trades = []
    order_mappings = []

    if hyperliquid_order_id:
        order_mappings.append((hyperliquid_order_id, "main"))
    if tp_order_id:
        order_mappings.append((tp_order_id, "tp"))
    if sl_order_id:
        order_mappings.append((sl_order_id, "sl"))

    if not order_mappings:
        return trades

    order_ids = [oid for oid, _ in order_mappings]
    trade_records = snapshot_db.query(HyperliquidTrade).filter(
        HyperliquidTrade.order_id.in_(order_ids)
    ).all()

    order_type_map = {oid: otype for oid, otype in order_mappings}

    for trade in trade_records:
        trades.append({
            "order_id": trade.order_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": float(trade.quantity) if trade.quantity else 0,
            "price": float(trade.price) if trade.price else 0,
            "leverage": trade.leverage,
            "trade_value": float(trade.trade_value) if trade.trade_value else 0,
            "fee": float(trade.fee) if trade.fee else 0,
            "trade_time": serialize_datetime(trade.trade_time),
            "order_type": order_type_map.get(trade.order_id, "unknown"),
            "environment": trade.environment,
            "wallet_address": trade.wallet_address,
        })

    return trades


def build_export_response(
    account_id: int,
    db: Session,
    snapshot_db: Session,
) -> JSONResponse:
    """Export all AI decision logs with related Hyperliquid trades for a trader."""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.is_deleted != True,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    decision_logs = db.query(AIDecisionLog).filter(
        AIDecisionLog.account_id == account_id
    ).order_by(AIDecisionLog.decision_time.asc()).all()

    export_data = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "account_name": account.name,
            "account_id": account_id,
        },
        "decision_logs": [],
    }

    for log in decision_logs:
        log_data = {
            "original_id": log.id,
            "decision_time": serialize_datetime(log.decision_time),
            "symbol": log.symbol,
            "operation": log.operation,
            "reason": log.reason,
            "prev_portion": float(log.prev_portion) if log.prev_portion else 0,
            "target_portion": float(log.target_portion) if log.target_portion else 0,
            "total_balance": float(log.total_balance) if log.total_balance else 0,
            "executed": log.executed,
            "prompt_snapshot": log.prompt_snapshot,
            "reasoning_snapshot": log.reasoning_snapshot,
            "decision_snapshot": log.decision_snapshot,
            "hyperliquid_environment": log.hyperliquid_environment,
            "wallet_address": log.wallet_address,
            "hyperliquid_order_id": log.hyperliquid_order_id,
            "tp_order_id": log.tp_order_id,
            "sl_order_id": log.sl_order_id,
            "realized_pnl": float(log.realized_pnl) if log.realized_pnl else None,
            "pnl_updated_at": serialize_datetime(log.pnl_updated_at),
            "created_at": serialize_datetime(log.created_at),
            "signal_trigger_id": log.signal_trigger_id,
            "prompt_template_id": log.prompt_template_id,
        }

        log_data["trades"] = get_related_trades(
            snapshot_db,
            log.hyperliquid_order_id,
            log.tp_order_id,
            log.sl_order_id,
        )
        export_data["decision_logs"].append(log_data)

    filename = f"{account.name.replace(' ', '_')}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/json",
        },
    )
