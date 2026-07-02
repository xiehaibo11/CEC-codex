"""HiBT account data endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth_dependencies import get_account_for_current_user, get_current_user
from database.connection import get_db
from database.models import HibtWallet, User
from services.hyperliquid_environment import get_global_trading_mode

from ._shared import _get_client, logger, router


def _resolve_wallet(db: Session, account_id: int, environment: str) -> HibtWallet:
    wallet = db.query(HibtWallet).filter(
        HibtWallet.account_id == account_id,
        HibtWallet.environment == environment,
        HibtWallet.is_active == "true",
    ).first()
    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} HiBT wallet configured")
    return wallet


@router.get("/accounts/{account_id}/balance")
def get_balance(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get HiBT perpetual futures account balance."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    try:
        return _get_client(wallet).get_account_state()
    except Exception as e:
        logger.error("Failed to get HiBT balance: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/positions")
def get_positions(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get HiBT perpetual futures open positions."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    try:
        return {"positions": _get_client(wallet).get_positions(), "environment": environment}
    except Exception as e:
        logger.error("Failed to get HiBT positions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/summary")
def get_account_summary(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get HiBT account summary for dashboard display."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    try:
        balance = _get_client(wallet).get_account_state()
        total_equity = balance.get("total_equity", 0.0)
        used_margin = balance.get("used_margin", 0.0)
        margin_usage = (used_margin / total_equity * 100) if total_equity > 0 else 0.0
        return {
            "account_id": account_id,
            "environment": environment,
            "exchange": "hibt",
            "equity": total_equity,
            "available_balance": balance.get("available_balance", 0.0),
            "used_margin": used_margin,
            "margin_usage": round(margin_usage, 1),
            "unrealized_pnl": balance.get("unrealized_pnl", 0.0),
            "rate_limit": None,
            "last_updated": None,
        }
    except Exception as e:
        logger.error("Failed to get HiBT account summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
