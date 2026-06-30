import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import AIDecisionLog, Trade
from repositories.account_repo import get_account
from repositories.order_repo import list_orders
from repositories.position_repo import list_positions
from services.asset_calculator import calc_positions_value
from services.asset_curve_calculator import get_all_asset_curves_data_new
from services.market_data import get_last_price

from .manager import manager

logger = logging.getLogger(__name__)


def get_all_asset_curves_data(
    db: Session,
    timeframe: str = "1h",
    trading_mode: str = "testnet",
    environment: Optional[str] = None,
    wallet_address: Optional[str] = None,
):
    """Get timeframe-based asset curve data for all accounts - WebSocket version

    Uses the new algorithm that draws curves by accounts and creates all-time lists.

    Args:
        timeframe: Time period for the curve, options: "5m", "1h", "1d"
        trading_mode: Trading mode filter, options: "paper", "testnet", "mainnet"
    """
    return get_all_asset_curves_data_new(
        db,
        timeframe,
        trading_mode,
        environment,
        wallet_address=wallet_address,
    )


async def _send_snapshot_optimized(db: Session, account_id: int):
    """Optimized version of snapshot that reduces expensive operations"""
    account = get_account(db, account_id)
    if not account:
        return

    positions = list_positions(db, account_id)
    orders = list_orders(db, account_id)
    trades = (
        db.query(Trade).filter(Trade.account_id == account_id).order_by(Trade.trade_time.desc()).limit(10).all()  # Reduced from 20 to 10
    )
    ai_decisions = (
        db.query(AIDecisionLog).filter(AIDecisionLog.account_id == account_id).order_by(AIDecisionLog.decision_time.desc()).limit(10).all()  # Reduced from 20 to 10
    )

    # Use cached positions value calculation
    positions_value = calc_positions_value(db, account_id)

    overview = {
        "account": {
            "id": account.id,
            "user_id": account.user_id,
            "name": account.name,
            "account_type": account.account_type,
            "initial_capital": float(account.initial_capital),
            "current_cash": float(account.current_cash),
            "frozen_cash": float(account.frozen_cash),
        },
        "total_assets": positions_value + float(account.current_cash),
        "positions_value": positions_value,
    }

    # Optimize position enrichment - batch price fetching
    enriched_positions = []
    price_error_message = None

    # Group positions by symbol to reduce API calls
    unique_symbols = set((p.symbol, p.market) for p in positions)
    price_cache = {}

    # Fetch all unique prices in one go
    for symbol, market in unique_symbols:
        try:
            price = get_last_price(symbol, market)
            price_cache[(symbol, market)] = price
        except Exception as e:
            price_cache[(symbol, market)] = None
            error_msg = str(e)
            if "cookie" in error_msg.lower() and price_error_message is None:
                price_error_message = error_msg

    for p in positions:
        price = price_cache.get((p.symbol, p.market))
        enriched_positions.append({
            "id": p.id,
            "account_id": p.account_id,
            "symbol": p.symbol,
            "name": p.name,
            "market": p.market,
            "quantity": float(p.quantity),
            "available_quantity": float(p.available_quantity),
            "avg_cost": float(p.avg_cost),
            "last_price": float(price) if price is not None else None,
            "market_value": (float(price) * float(p.quantity)) if price is not None else None,
        })

    # Prepare response data - exclude expensive asset curve calculation for frequent updates
    response_data = {
        "type": "snapshot_fast",  # Different type to indicate this is optimized
        "overview": overview,
        "positions": enriched_positions,
        "orders": [
            {
                "id": o.id,
                "order_no": o.order_no,
                "user_id": o.account_id,
                "symbol": o.symbol,
                "name": o.name,
                "market": o.market,
                "side": o.side,
                "order_type": o.order_type,
                "price": float(o.price) if o.price is not None else None,
                "quantity": float(o.quantity),
                "filled_quantity": float(o.filled_quantity),
                "status": o.status,
            }
            for o in orders[:10]  # Reduced from 20 to 10
        ],
        "trades": [
            {
                "id": t.id,
                "order_id": t.order_id,
                "user_id": t.account_id,
                "symbol": t.symbol,
                "name": t.name,
                "market": t.market,
                "side": t.side,
                "price": float(t.price),
                "quantity": float(t.quantity),
                "commission": float(t.commission),
                "trade_time": str(t.trade_time),
            }
            for t in trades
        ],
        "ai_decisions": [
            {
                "id": d.id,
                "decision_time": str(d.decision_time),
                "reason": d.reason,
                "operation": d.operation,
                "symbol": d.symbol,
                "prev_portion": float(d.prev_portion),
                "target_portion": float(d.target_portion),
                "total_balance": float(d.total_balance),
                "executed": str(d.executed).lower() if d.executed else "false",
                "order_id": d.order_id,
            }
            for d in ai_decisions
        ],
        # Asset curves only included occasionally (every minute)
        "timestamp": datetime.utcnow().timestamp()
    }

    # Only include expensive asset curve data every 60 seconds
    current_second = int(datetime.utcnow().timestamp()) % 60
    if current_second < 10:  # First 10 seconds of each minute
        try:
            response_data["all_asset_curves"] = get_all_asset_curves_data(db, "1h")
            response_data["type"] = "snapshot_full"  # Indicate this includes full data
        except Exception as e:
            logger.error(f"Failed to get asset curves: {e}")

    if price_error_message:
        response_data["warning"] = {
            "type": "market_data_error",
            "message": price_error_message
        }

    await manager.send_to_account(account_id, response_data)


async def _send_snapshot(db: Session, account_id: int):
    account = get_account(db, account_id)
    if not account:
        return
    positions = list_positions(db, account_id)
    orders = list_orders(db, account_id)
    trades = (
        db.query(Trade).filter(Trade.account_id == account_id).order_by(Trade.trade_time.desc()).limit(20).all()
    )
    ai_decisions = (
        db.query(AIDecisionLog).filter(AIDecisionLog.account_id == account_id).order_by(AIDecisionLog.decision_time.desc()).limit(20).all()
    )
    positions_value = calc_positions_value(db, account_id)

    overview = {
        "account": {
            "id": account.id,
            "user_id": account.user_id,
            "name": account.name,
            "account_type": account.account_type,
            "initial_capital": float(account.initial_capital),
            "current_cash": float(account.current_cash),
            "frozen_cash": float(account.frozen_cash),
        },
        "total_assets": positions_value + float(account.current_cash),
        "positions_value": positions_value,
    }
    # enrich positions with latest price and market value
    enriched_positions = []
    price_error_message = None

    for p in positions:
        try:
            price = get_last_price(p.symbol, p.market)
        except Exception as e:
            price = None
            # Collect price retrieval error messages, especially cookie-related errors
            error_msg = str(e)
            if "cookie" in error_msg.lower() and price_error_message is None:
                price_error_message = error_msg

        enriched_positions.append({
            "id": p.id,
            "account_id": p.account_id,
            "symbol": p.symbol,
            "name": p.name,
            "market": p.market,
            "quantity": float(p.quantity),
            "available_quantity": float(p.available_quantity),
            "avg_cost": float(p.avg_cost),
            "last_price": float(price) if price is not None else None,
            "market_value": (float(price) * float(p.quantity)) if price is not None else None,
        })

    # Prepare response data
    response_data = {
        "type": "snapshot",
        "overview": overview,
        "positions": enriched_positions,
        "orders": [
            {
                "id": o.id,
                "order_no": o.order_no,
                "user_id": o.account_id,
                "symbol": o.symbol,
                "name": o.name,
                "market": o.market,
                "side": o.side,
                "order_type": o.order_type,
                "price": float(o.price) if o.price is not None else None,
                "quantity": float(o.quantity),
                "filled_quantity": float(o.filled_quantity),
                "status": o.status,
            }
            for o in orders[:20]
        ],
        "trades": [
            {
                "id": t.id,
                "order_id": t.order_id,
                "user_id": t.account_id,
                "symbol": t.symbol,
                "name": t.name,
                "market": t.market,
                "side": t.side,
                "price": float(t.price),
                "quantity": float(t.quantity),
                "commission": float(t.commission),
                "trade_time": str(t.trade_time),
            }
            for t in trades
        ],
        "ai_decisions": [
            {
                "id": d.id,
                "decision_time": str(d.decision_time),
                "reason": d.reason,
                "operation": d.operation,
                "symbol": d.symbol,
                "prev_portion": float(d.prev_portion),
                "target_portion": float(d.target_portion),
                "total_balance": float(d.total_balance),
                "executed": str(d.executed).lower() if d.executed else "false",
                "order_id": d.order_id,
            }
            for d in ai_decisions
        ],
        "all_asset_curves": get_all_asset_curves_data(db, "1h"),
    }

    if price_error_message:
        response_data["warning"] = {
            "type": "market_data_error",
            "message": price_error_message
        }

    await manager.send_to_account(account_id, response_data)
