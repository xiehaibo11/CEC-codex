import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from repositories.account_repo import get_account, get_or_create_default_account
from repositories.user_repo import get_or_create_user, get_user

from .hyperliquid_snapshots import _send_snapshot_by_mode
from .manager import manager
from .snapshots import _send_snapshot, get_all_asset_curves_data


async def websocket_endpoint(websocket: WebSocket):
    client_host = websocket.client.host if websocket.client else "unknown"
    logging.info(f"[WS] New WebSocket connection from {client_host}")
    await websocket.accept()
    logging.info(f"[WS] WebSocket connection accepted from {client_host}")
    try:
        manager.set_event_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass
    account_id: int | None = None
    user_id: int | None = None  # Initialize user_id to avoid UnboundLocalError

    try:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                # Client disconnected gracefully
                break
            except Exception as e:
                # Handle other connection errors
                logging.error(f"WebSocket receive error: {e}")
                break

            try:
                msg = json.loads(data)
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON received: {e}")
                try:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON format"}))
                except:
                    break
                continue
            kind = msg.get("type")
            logging.info(f"[WS] Received message type: {kind}")
            db: Session = SessionLocal()
            try:
                if kind == "bootstrap":
                    #  mode: Create or get default default user
                    username = msg.get("username", "default")
                    trading_mode = msg.get("trading_mode", "paper")
                    logging.info(f"[WS] Bootstrap request: username={username}, trading_mode={trading_mode}")
                    user = get_or_create_user(db, username)

                    # Get existing account for this user
                    account = get_or_create_default_account(
                        db,
                        user.id,
                        account_name=f"{username} AI Trader",
                        initial_capital=float(msg.get("initial_capital", 100000))
                    )

                    if not account:
                        # Allow connection but with no account (frontend will handle this)
                        account_id = None
                    else:
                        account_id = account.id

                    # Register the connection (handles None account_id gracefully)
                    manager.register(account_id, websocket)
                    logging.info(f"[WS] Registered connection for account_id={account_id}")

                    # Send bootstrap confirmation with account info
                    try:
                        if account:
                            logging.info(f"[WS] Sending bootstrap_ok for account {account.id}")
                            await manager.send_to_account(account_id, {
                                "type": "bootstrap_ok",
                                "user": {"id": user.id, "username": user.username},
                                "account": {"id": account.id, "name": account.name, "user_id": account.user_id}
                            })
                            logging.info(f"[WS] Sending snapshot for account {account.id}")
                            await _send_snapshot(db, account_id)
                            logging.info(f"[WS] Bootstrap complete for account {account.id}")
                        else:
                            # Send bootstrap with no account info
                            await websocket.send_text(json.dumps({
                                "type": "bootstrap_ok",
                                "user": {"id": user.id, "username": user.username},
                                "account": None
                            }))
                    except Exception as e:
                        logging.error(f"Failed to send bootstrap response: {e}")
                        break
                elif kind == "subscribe":
                    # subscribe existing user_id
                    uid = int(msg.get("user_id"))
                    u = get_user(db, uid)
                    if not u:
                        try:
                            await websocket.send_text(json.dumps({"type": "error", "message": "user not found"}))
                        except:
                            break
                        continue
                    user_id = uid
                    manager.register(user_id, websocket)
                    try:
                        await _send_snapshot(db, user_id)
                    except Exception as e:
                        logging.error(f"Failed to send snapshot: {e}")
                        break
                elif kind == "switch_user":
                    # Switch to different user account
                    target_username = msg.get("username")
                    if not target_username:
                        await websocket.send_text(json.dumps({"type": "error", "message": "username required"}))
                        continue

                    # Unregister from current user if any
                    if user_id is not None:
                        manager.unregister(user_id, websocket)

                    # Find target user
                    target_user = get_or_create_user(db, target_username, 100000.0)
                    user_id = target_user.id

                    # Register to new user
                    manager.register(user_id, websocket)

                    # Send confirmation and snapshot
                    await manager.send_to_account(user_id, {
                        "type": "user_switched",
                        "user": {
                            "id": target_user.id,
                            "username": target_user.username
                        }
                    })
                    await _send_snapshot(db, user_id)
                elif kind == "switch_account":
                    # Switch to different account by ID
                    target_account_id = msg.get("account_id")
                    if not target_account_id:
                        await websocket.send_text(json.dumps({"type": "error", "message": "account_id required"}))
                        continue

                    # Unregister from current account if any
                    if account_id is not None:
                        manager.unregister(account_id, websocket)

                    # Get target account
                    target_account = get_account(db, target_account_id)
                    if not target_account:
                        await websocket.send_text(json.dumps({"type": "error", "message": "account not found"}))
                        continue

                    account_id = target_account.id

                    # Register to new account
                    manager.register(account_id, websocket)

                    # Send confirmation and snapshot
                    await manager.send_to_account(account_id, {
                        "type": "account_switched",
                        "account": {
                            "id": target_account.id,
                            "user_id": target_account.user_id,
                            "name": target_account.name
                        }
                    })
                    await _send_snapshot(db, account_id)
                elif kind == "get_snapshot":
                    if account_id is not None:
                        # Get trading mode from request (default to "testnet")
                        trading_mode = msg.get("trading_mode", "testnet")
                        logging.info(f"Received get_snapshot request: account_id={account_id}, trading_mode={trading_mode}")
                        await _send_snapshot_by_mode(db, account_id, trading_mode)
                elif kind == "get_asset_curve":
                    # Get asset curve data with specific timeframe and trading mode
                    timeframe = msg.get("timeframe", "1h")
                    trading_mode = msg.get("trading_mode", "testnet")
                    environment = msg.get("environment")
                    if timeframe not in ["5m", "1h", "1d"]:
                        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid timeframe. Must be 5m, 1h, or 1d"}))
                        continue

                    asset_curves = get_all_asset_curves_data(
                        db,
                        timeframe,
                        trading_mode,
                        environment=environment,
                    )
                    await websocket.send_text(json.dumps({
                        "type": "asset_curve_data",
                        "timeframe": timeframe,
                        "trading_mode": trading_mode,
                        "environment": environment,
                        "data": asset_curves
                    }))
                elif kind == "place_order":
                    if account_id is None:
                        await websocket.send_text(json.dumps({"type": "error", "message": "not authenticated"}))
                        continue

                    try:
                        # Import the order creation service
                        from services.order_matching import create_order

                        # Get account and user object
                        account = get_account(db, account_id)
                        if not account:
                            await websocket.send_text(json.dumps({"type": "error", "message": "account not found"}))
                            continue

                        user = get_user(db, account.user_id)
                        if not user:
                            await websocket.send_text(json.dumps({"type": "error", "message": "user not found"}))
                            continue

                        # Extract order parameters
                        symbol = msg.get("symbol")
                        name = msg.get("name", symbol)  # Use symbol as name if not provided
                        market = msg.get("market", "CRYPTO")
                        side = msg.get("side")
                        order_type = msg.get("order_type")
                        price = msg.get("price")
                        quantity = msg.get("quantity")

                        # Validate required parameters
                        if not all([symbol, side, order_type, quantity]):
                            await websocket.send_text(json.dumps({"type": "error", "message": "missing required parameters"}))
                            continue

                        # Convert quantity to float (crypto supports fractional quantities)
                        try:
                            quantity = float(quantity)
                        except (ValueError, TypeError):
                            await websocket.send_text(json.dumps({"type": "error", "message": "invalid quantity"}))
                            continue

                        # Create the order
                        order = create_order(
                            db=db,
                            account=account,
                            symbol=symbol,
                            name=name,
                            side=side,
                            order_type=order_type,
                            price=price,
                            quantity=quantity
                        )

                        # Commit the order
                        db.commit()

                        # Send success response
                        await manager.send_to_account(account_id, {"type": "order_pending", "order_id": order.id})

                        # Send updated snapshot
                        await _send_snapshot(db, account_id)

                    except ValueError as e:
                        # Business logic errors (insufficient funds, etc.)
                        try:
                            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
                        except:
                            break
                    except Exception as e:
                        # Unexpected errors
                        import traceback
                        print(f"Order placement error: {e}")
                        print(traceback.format_exc())
                        try:
                            await websocket.send_text(json.dumps({"type": "error", "message": f"order placement failed: {str(e)}"}))
                        except:
                            break
                elif kind == "ping":
                    try:
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    except:
                        break
                else:
                    try:
                        await websocket.send_text(json.dumps({"type": "error", "message": "unknown message"}))
                    except:
                        break
            finally:
                db.close()
    except WebSocketDisconnect:
        if account_id is not None:
            manager.unregister(account_id, websocket)
        if user_id is not None:
            manager.unregister(user_id, websocket)
        return
    finally:
        # Clean up resources when user disconnects
        if account_id is not None:
            manager.unregister(account_id, websocket)
        if user_id is not None:
            manager.unregister(user_id, websocket)
