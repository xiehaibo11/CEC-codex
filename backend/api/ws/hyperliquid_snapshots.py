import logging

from sqlalchemy.orm import Session

from database.models import AIDecisionLog, Trade
from repositories.account_repo import get_account
from repositories.order_repo import list_orders
from services.hyperliquid_cache import get_cached_account_state, get_cached_positions
from services.hyperliquid_environment import get_hyperliquid_client

from .manager import manager
from .snapshots import _send_snapshot, get_all_asset_curves_data

HYPERLIQUID_SNAPSHOT_CACHE_TTL = 360  # seconds


async def _send_snapshot_by_mode(db: Session, account_id: int, trading_mode: str):
    """
    Send snapshot based on trading mode

    Args:
        db: Database session
        account_id: Account ID
        trading_mode: "paper", "testnet", or "mainnet"
    """
    logging.info(f"_send_snapshot_by_mode called: trading_mode={trading_mode}, account_id={account_id}")
    if trading_mode == "paper":
        # Use traditional paper trading snapshot
        logging.info(f"Sending paper trading snapshot for account {account_id}")
        await _send_snapshot(db, account_id)
    elif trading_mode in ["testnet", "mainnet"]:
        # Use Hyperliquid real-time snapshot
        logging.info(f"Sending Hyperliquid {trading_mode} snapshot for account {account_id}")
        await _send_hyperliquid_snapshot(db, account_id, trading_mode)
    else:
        logging.error(f"Invalid trading_mode: {trading_mode}")
        await _send_snapshot(db, account_id)  # Fallback to paper


async def _send_hyperliquid_snapshot(db: Session, account_id: int, environment: str):
    """
    Send Hyperliquid snapshot, preferring cached data to avoid unnecessary API calls.

    Args:
        db: Database session
        account_id: Account ID
        environment: "testnet" or "mainnet"
    """

    account = get_account(db, account_id)
    if not account:
        logging.error(f"Account {account_id} not found for Hyperliquid snapshot")
        return

    # Check if wallet exists for this environment (multi-wallet architecture)
    from database.models import HyperliquidWallet
    wallet = db.query(HyperliquidWallet).filter(
        HyperliquidWallet.account_id == account_id,
        HyperliquidWallet.environment == environment
    ).first()

    if not wallet:
        # Silently skip sending error to avoid spamming frontend
        # Just log the warning
        logging.debug(f"No {environment} wallet configured for account {account.name} (ID: {account_id})")
        return

    cached_state = get_cached_account_state(account_id, environment, max_age_seconds=HYPERLIQUID_SNAPSHOT_CACHE_TTL)
    cached_positions = get_cached_positions(account_id, environment, max_age_seconds=HYPERLIQUID_SNAPSHOT_CACHE_TTL)
    account_state = cached_state["data"] if cached_state else None
    positions_data = cached_positions["data"] if cached_positions else None
    wallet_address = None
    if isinstance(account_state, dict):
        wallet_address = account_state.get("wallet_address")

    data_source = "cache"
    client = None

    if account_state is None or positions_data is None:
        try:
            client = get_hyperliquid_client(db, account_id, override_environment=environment)
        except Exception as e:
            logging.warning(f"Failed to initialize Hyperliquid client for account {account.name} ({environment}): {e}")
            # Don't send error to frontend, just log and skip
            return

        try:
            account_state = client.get_account_state(db)
            positions_data = client.get_positions(db)
            wallet_address = client.wallet_address
            data_source = "live"
        except Exception as e:
            logging.error(f"Failed to fetch Hyperliquid data for account {account_id}: {e}", exc_info=True)
            await manager.send_to_account(account_id, {
                "type": "error",
                "message": f"Failed to fetch Hyperliquid data: {str(e)}"
            })
            return
    else:
        # Cache hit but wallet missing? fall back to client for metadata only.
        if wallet_address is None:
            try:
                client = get_hyperliquid_client(db, account_id)
                if client.environment == environment:
                    wallet_address = client.wallet_address
            except Exception:
                wallet_address = None

    if account_state is None or positions_data is None:
        logging.error(f"Hyperliquid snapshot missing state or positions for account {account_id}")
        return

    wallet_address = wallet_address or account_state.get("wallet_address")

    try:
        # Transform Hyperliquid data to frontend format
        overview = {
            "account": {
                "id": account.id,
                "user_id": account.user_id,
                "name": account.name,
                "account_type": f"hyperliquid_{environment}",
                "initial_capital": float(account.initial_capital),
                # Use Hyperliquid balance instead of local database
                "current_cash": account_state.get("available_balance", 0),
                "frozen_cash": account_state.get("used_margin", 0),
            },
            "total_assets": account_state.get("total_equity", 0),
            "positions_value": sum(
                abs(p.get("position_value", 0)) for p in positions_data
            ),
        }

        # Transform Hyperliquid positions to frontend format
        enriched_positions = []
        for p in positions_data:
            enriched_positions.append({
                "id": 0,  # Hyperliquid positions don't have local DB ID
                "account_id": account_id,
                "symbol": p.get("coin", ""),
                "name": p.get("coin", ""),
                "market": "HYPERLIQUID_PERP",
                "quantity": abs(p.get("szi", 0)),  # Absolute size
                "available_quantity": abs(p.get("szi", 0)),
                "avg_cost": p.get("entry_px", 0),
                "last_price": None,  # Can fetch from market data if needed
                "market_value": p.get("position_value", 0),
                "current_value": p.get("position_value", 0),
                "unrealized_pnl": p.get("unrealized_pnl", 0),
                "leverage": p.get("leverage", 1),
                "side": "LONG" if p.get("szi", 0) > 0 else "SHORT",
            })

        # Get orders and trades from local database (filtered by environment)
        orders = list_orders(db, account_id)
        # Filter orders by hyperliquid_environment
        hyperliquid_orders = [
            o for o in orders
            if o.hyperliquid_environment == environment
        ]

        trades = (
            db.query(Trade)
            .filter(Trade.account_id == account_id)
            .filter(Trade.hyperliquid_environment == environment)
            .order_by(Trade.trade_time.desc())
            .limit(20)
            .all()
        )

        ai_decisions = (
            db.query(AIDecisionLog)
            .filter(AIDecisionLog.account_id == account_id)
            .filter(AIDecisionLog.hyperliquid_environment == environment)
            .order_by(AIDecisionLog.decision_time.desc())
            .limit(20)
            .all()
        )

        # Prepare response data
        response_data = {
            "type": "snapshot",
            "trading_mode": environment,
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
                for o in hyperliquid_orders[:20]
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
            "all_asset_curves": get_all_asset_curves_data(
                db,
                "1h",
                trading_mode=environment,
                environment=environment,
            ),
            "hyperliquid_state": {
                "environment": environment,
                "total_equity": account_state.get("total_equity", 0),
                "available_balance": account_state.get("available_balance", 0),
                "used_margin": account_state.get("used_margin", 0),
                "margin_usage_percent": account_state.get("margin_usage_percent", 0),
                "source": data_source,
                "wallet_address": wallet_address,
            }
        }

        await manager.send_to_account(account_id, response_data)

    except Exception as e:
        logging.error(f"Failed to get Hyperliquid snapshot: {e}", exc_info=True)
        await manager.send_to_account(account_id, {
            "type": "error",
            "message": f"Failed to fetch Hyperliquid data: {str(e)}"
        })
