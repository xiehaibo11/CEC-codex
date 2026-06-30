import logging

from database.connection import SessionLocal

from .manager import manager
from .snapshots import get_all_asset_curves_data


async def broadcast_asset_curve_update(timeframe: str = "1h"):
    """Broadcast asset curve updates to all connected clients"""
    db = SessionLocal()
    try:
        asset_curves = get_all_asset_curves_data(db, timeframe)
        await manager.broadcast_to_all({
            "type": "asset_curve_update",
            "timeframe": timeframe,
            "data": asset_curves
        })
    except Exception as e:
        logging.error(f"Failed to broadcast asset curve update: {e}")
    finally:
        db.close()


async def broadcast_arena_asset_update(update_payload: dict):
    """Broadcast aggregated arena asset update to all connected clients"""
    message = {
        "type": "arena_asset_update",
        **update_payload,
    }
    await manager.broadcast_to_all(message)


async def broadcast_trade_update(trade_data: dict):
    """Broadcast trade update to specific account when trade is executed

    Args:
        trade_data: Dictionary containing trade information including account_id
    """
    account_id = trade_data.get("account_id")
    if not account_id:
        logging.warning("broadcast_trade_update called without account_id")
        return

    try:
        await manager.send_to_account(account_id, {
            "type": "trade_update",
            "trade": trade_data
        })
    except Exception as e:
        logging.error(f"Failed to broadcast trade update: {e}")


async def broadcast_position_update(account_id: int, positions_data: list):
    """Broadcast position update to specific account when positions change

    Args:
        account_id: Account ID to send update to
        positions_data: List of position dictionaries
    """
    try:
        await manager.send_to_account(account_id, {
            "type": "position_update",
            "positions": positions_data
        })
    except Exception as e:
        logging.error(f"Failed to broadcast position update: {e}")


async def broadcast_model_chat_update(decision_data: dict):
    """Broadcast AI decision update to specific account

    Args:
        decision_data: Dictionary containing AI decision information including account_id
    """
    account_id = decision_data.get("account_id")
    if not account_id:
        logging.warning("broadcast_model_chat_update called without account_id")
        return

    try:
        await manager.send_to_account(account_id, {
            "type": "model_chat_update",
            "decision": decision_data
        })
    except Exception as e:
        logging.error(f"Failed to broadcast model chat update: {e}")
