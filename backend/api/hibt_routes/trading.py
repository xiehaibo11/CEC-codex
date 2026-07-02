"""HiBT manual trading endpoints: order placement and position closing."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth_dependencies import get_account_for_current_user, get_current_user
from database.connection import get_db
from database.models import HibtWallet, User
from services.hyperliquid_environment import get_global_trading_mode

from ._shared import _get_client, logger, router


class ManualOrderRequest(BaseModel):
    """Request model for manual HiBT order placement."""

    symbol: str = Field(..., description="Asset symbol, e.g. BTC")
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    order_type: str = Field("MARKET", pattern="^(MARKET|LIMIT)$", alias="orderType")
    price: Optional[float] = Field(None, gt=0)
    leverage: int = Field(1, ge=1, le=125)
    reduce_only: bool = Field(False, alias="reduceOnly")
    take_profit_price: Optional[float] = Field(None, gt=0, alias="takeProfitPrice")
    stop_loss_price: Optional[float] = Field(None, gt=0, alias="stopLossPrice")

    class Config:
        populate_by_name = True


def _resolve_wallet(db: Session, account_id: int, environment: str) -> HibtWallet:
    wallet = db.query(HibtWallet).filter(
        HibtWallet.account_id == account_id,
        HibtWallet.environment == environment,
        HibtWallet.is_active == "true",
    ).first()
    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} HiBT wallet configured")
    return wallet


@router.post("/accounts/{account_id}/order")
def place_order(
    account_id: int,
    request: ManualOrderRequest,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place a manual order on HiBT perpetual futures."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    if request.leverage > wallet.max_leverage:
        raise HTTPException(
            status_code=400,
            detail=f"Leverage {request.leverage} exceeds max {wallet.max_leverage}",
        )

    try:
        client = _get_client(wallet)
        if request.reduce_only:
            position = _find_position(client.get_positions(request.symbol), request.symbol)
            if not position:
                return {"message": f"No position to close for {request.symbol}"}
            quantity = min(abs(float(position.get("szi") or 0)), request.quantity)
            return client.close_position(
                position_id=str(position.get("position_id")),
                quantity=quantity,
                order_type=request.order_type,
                price=request.price,
            )

        return client.place_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            leverage=request.leverage,
            take_profit_price=request.take_profit_price,
            stop_loss_price=request.stop_loss_price,
        )
    except Exception as e:
        logger.error("HiBT order failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/{account_id}/close-position")
def close_position(
    account_id: int,
    symbol: str,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close entire HiBT position for a symbol."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)
    wallet = _resolve_wallet(db, account_id, environment)

    try:
        client = _get_client(wallet)
        position = _find_position(client.get_positions(symbol), symbol)
        if not position:
            return {"message": f"No position to close for {symbol}"}
        position_id = position.get("position_id")
        quantity = abs(float(position.get("szi") or 0))
        if not position_id or quantity <= 0:
            return {"message": f"No closable position to close for {symbol}"}
        return client.close_position(position_id=str(position_id), quantity=quantity)
    except Exception as e:
        logger.error("HiBT close position failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _find_position(positions: list[dict], symbol: str) -> dict | None:
    requested = symbol.upper()
    for position in positions:
        if str(position.get("coin") or position.get("symbol") or "").upper() != requested:
            continue
        if abs(float(position.get("szi") or 0)) <= 0:
            continue
        return position
    return None
