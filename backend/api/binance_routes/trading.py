"""
Binance manual trading endpoints: order placement and position closing.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from database.connection import get_db
from database.models import BinanceWallet, User
from api.auth_dependencies import get_current_user, get_account_for_current_user
from services.hyperliquid_environment import get_global_trading_mode
from services.binance_testnet_order_probe import run_binance_testnet_order_probe

from ._shared import router, logger, _get_client


class ManualOrderRequest(BaseModel):
    """Request model for manual order placement"""
    symbol: str = Field(..., description="Asset symbol (e.g., 'BTC')")
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


class TestnetOrderProbeRequest(BaseModel):
    """Small Binance Futures Testnet order that is cancelled immediately."""

    symbol: str = Field("BTC", description="Asset symbol (e.g., 'BTC')")
    side: str = Field("SELL", pattern="^(BUY|SELL)$")
    quantity: float = Field(0.001, gt=0)
    leverage: int = Field(1, ge=1, le=125)
    price_offset_pct: float = Field(5.0, ge=0.1, le=20, alias="priceOffsetPct")

    class Config:
        populate_by_name = True


@router.post("/accounts/{account_id}/testnet-order-probe")
def place_testnet_order_probe(
    account_id: int,
    request: TestnetOrderProbeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place and immediately cancel a real Binance Futures Testnet limit order."""

    get_account_for_current_user(account_id, current_user, db)

    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == "testnet",
        BinanceWallet.is_active == "true",
    ).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="No testnet wallet configured")

    try:
        return run_binance_testnet_order_probe(
            wallet=wallet,
            client=_get_client(wallet),
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            leverage=request.leverage,
            price_offset_pct=request.price_offset_pct,
        )
    except Exception as e:
        logger.error(f"Binance testnet order probe failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/{account_id}/order")
def place_order(
    account_id: int,
    request: ManualOrderRequest,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Place a manual order on Binance Futures"""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)

    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == environment,
        BinanceWallet.is_active == "true"
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} wallet configured")

    # Validate leverage
    if request.leverage > wallet.max_leverage:
        raise HTTPException(
            status_code=400,
            detail=f"Leverage {request.leverage} exceeds max {wallet.max_leverage}"
        )

    try:
        client = _get_client(wallet)

        # Use unified place_order_with_tpsl method (same as AI Trader and Program Trader)
        is_buy = request.side.upper() == "BUY"
        result = client.place_order_with_tpsl(
            db=db,
            symbol=request.symbol,
            is_buy=is_buy,
            size=request.quantity,
            price=request.price or 0,
            leverage=request.leverage,
            time_in_force="GTC",
            reduce_only=request.reduce_only,
            take_profit_price=request.take_profit_price,
            stop_loss_price=request.stop_loss_price,
            order_type=request.order_type,
            tp_execution="market",  # Manual orders default to market execution
            sl_execution="market",
        )

        # Map result to API response format
        return {
            "order_id": result.get("order_id"),
            "status": result.get("status"),
            "filled_qty": result.get("filled_qty"),
            "avg_price": result.get("avg_price"),
            "environment": result.get("environment"),
            "tp_order": {"algo_id": result.get("tp_order_id")} if result.get("tp_order_id") else None,
            "sl_order": {"algo_id": result.get("sl_order_id")} if result.get("sl_order_id") else None,
            "errors": result.get("errors", []),
        }
    except Exception as e:
        logger.error(f"Order failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/{account_id}/close-position")
def close_position(
    account_id: int,
    symbol: str,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Close entire position for a symbol"""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)

    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == environment,
        BinanceWallet.is_active == "true"
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} wallet configured")

    try:
        client = _get_client(wallet)
        result = client.close_position(symbol)
        if result is None:
            return {"message": f"No position to close for {symbol}"}
        return result
    except Exception as e:
        logger.error(f"Close position failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
