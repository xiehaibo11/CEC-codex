from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Account, HyperliquidExchangeAction, User
from api.auth_dependencies import get_account_for_current_user, get_current_user

router = APIRouter(prefix="/api/hyperliquid/actions", tags=["Hyperliquid Actions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _serialize_action(
    action: HyperliquidExchangeAction,
    *,
    include_payloads: bool = False,
) -> Dict[str, Any]:
    data = {
        "id": action.id,
        "timestamp": action.created_at.isoformat() if action.created_at else None,
        "account_id": action.account_id,
        "environment": action.environment,
        "wallet_address": action.wallet_address,
        "action_type": action.action_type,
        "status": action.status,
        "symbol": action.symbol,
        "side": action.side,
        "leverage": action.leverage,
        "size": float(action.size) if action.size is not None else None,
        "price": float(action.price) if action.price is not None else None,
        "notional": float(action.notional) if action.notional is not None else None,
        "request_weight": action.request_weight,
        "error_message": action.error_message,
    }
    if include_payloads:
        data["request_payload"] = action.request_payload
        data["response_payload"] = action.response_payload
    return data


@router.get("/")
def list_exchange_actions(
    limit: int = Query(100, ge=1, le=500),
    account_id: Optional[int] = Query(None),
    environment: Optional[str] = Query(None, regex="^(testnet|mainnet)$"),
    wallet_address: Optional[str] = Query(None),
    include_payloads: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(HyperliquidExchangeAction)

    if account_id is not None:
        get_account_for_current_user(account_id, current_user, db, active_only=False)
        query = query.filter(HyperliquidExchangeAction.account_id == account_id)
    else:
        owned_account_ids = db.query(Account.id).filter(
            Account.user_id == current_user.id,
            Account.is_deleted != True,
        ).subquery()
        query = query.filter(HyperliquidExchangeAction.account_id.in_(owned_account_ids))

    if environment is not None:
        query = query.filter(HyperliquidExchangeAction.environment == environment)
    if wallet_address is not None:
        query = query.filter(HyperliquidExchangeAction.wallet_address == wallet_address)

    total = query.count()

    entries = (
        query.order_by(HyperliquidExchangeAction.created_at.desc())
        .limit(limit)
        .all()
    )

    success_count = (
        query.filter(HyperliquidExchangeAction.status == "success").count()
    )
    error_count = (
        query.filter(HyperliquidExchangeAction.status == "error").count()
    )
    request_weight_sum = (
        query.with_entities(
            func.coalesce(func.sum(HyperliquidExchangeAction.request_weight), 0)
        ).scalar()
    )

    last_24h = (
        query.filter(
            HyperliquidExchangeAction.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
    )

    return {
        "entries": [
            _serialize_action(entry, include_payloads=include_payloads)
            for entry in entries
        ],
        "stats": {
            "total": total,
            "success": success_count,
            "error": error_count,
            "last24h": last_24h,
            "request_weight_sum": request_weight_sum,
        },
    }
