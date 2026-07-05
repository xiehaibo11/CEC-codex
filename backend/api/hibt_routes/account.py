"""HiBT account data endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth_dependencies import get_account_for_current_user, get_current_user
from database.connection import get_db
from database.models import User
from services.hyperliquid_environment import get_global_trading_mode

from ._shared import _get_client, _resolve_wallet, logger, router


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


@router.get("/accounts/{account_id}/trades")
def get_trade_history(
    account_id: int,
    symbol: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: Optional[int] = Query(None, le=1000),
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get HiBT account trade history for a symbol (start/end in seconds)."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    try:
        trades = _get_client(wallet).get_trade_history(
            symbol=symbol, start_time=start_time, end_time=end_time, limit=limit
        )
        return {"trades": trades, "environment": environment}
    except Exception as e:
        logger.error("Failed to get HiBT trade history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/balance-records")
def get_balance_records(
    account_id: int,
    symbol: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    event: Optional[int] = None,
    limit: Optional[int] = Query(None, le=1000),
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get HiBT balance change records (ms timestamps, 30-day window)."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    try:
        records = _get_client(wallet).get_balance_records(
            symbol=symbol, start_time=start_time, end_time=end_time, event=event, limit=limit
        )
        return {"records": records, "environment": environment}
    except Exception as e:
        logger.error("Failed to get HiBT balance records: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/liquidations")
def get_forced_liquidations(
    account_id: int,
    symbol: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    action: Optional[int] = None,
    limit: Optional[int] = Query(None, le=1000),
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get HiBT forced-liquidation history (ms timestamps, 7-day window)."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    try:
        records = _get_client(wallet).get_forced_liquidations(
            symbol=symbol, start_time=start_time, end_time=end_time, action=action, limit=limit
        )
        return {"records": records, "environment": environment}
    except Exception as e:
        logger.error("Failed to get HiBT liquidation history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
