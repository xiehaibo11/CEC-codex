"""
Trading Commands - single Binance AI-decision execution.

``_execute_binance_decision`` validates and executes one AI decision on
Binance Futures (operation/leverage/quota/sizing checks, order placement,
trade-record persistence). Logic is preserved exactly as the original
``trading_commands`` implementation.
"""
import logging
from typing import Dict, Optional, Any, List

from sqlalchemy.orm import Session

from database.models import Account
from services.ai_decision_service import save_ai_decision

from .helpers import _check_binance_daily_quota


logger = logging.getLogger(__name__)


def _execute_binance_decision(
    db: Session,
    account: Account,
    client,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    available_balance: float = 0.0,
    max_leverage: int = 20,
    default_leverage: int = 5,
    decision_kwargs: Optional[Dict[str, Any]] = None,
    wallet=None,
    trigger_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Execute a single AI decision on Binance.

    Uses the same logic as Hyperliquid:
    - Validates operation type
    - Calculates quantity from target_portion_of_balance
    - Validates leverage range
    - Places order with TP/SL via place_order_with_tpsl()
    - Records order IDs for attribution
    """
    # Default decision_kwargs if not provided
    if decision_kwargs is None:
        decision_kwargs = {}

    operation = decision.get("operation", "").lower()
    symbol = decision.get("symbol", "").upper() if decision.get("symbol") else ""
    target_portion = float(decision.get("target_portion_of_balance", 0))
    leverage = int(decision.get("leverage", default_leverage))
    reason = decision.get("reason", "No reason provided")

    # Extract TP/SL from AI decision
    take_profit_price = decision.get("take_profit_price")
    stop_loss_price = decision.get("stop_loss_price")

    logger.info(
        f"[BINANCE] AI decision for {account.name}: {operation} {symbol} "
        f"(portion: {target_portion:.2%}, leverage: {leverage}x) - {reason}"
    )

    # 1. Validate operation type
    if operation not in ["buy", "sell", "hold", "close"]:
        logger.warning(f"[BINANCE] Invalid operation '{operation}' from AI for {account.name}")
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    # 2. Handle HOLD operation (no quota consumption, no execution needed)
    if operation == "hold":
        logger.info(f"[BINANCE] AI decided to HOLD for {account.name} - no action taken")
        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
        return

    # 3. Check daily quota for mainnet non-rebate accounts (only for buy/sell/close)
    if wallet and wallet.environment == "mainnet" and wallet.rebate_working is False:
        quota_exceeded, quota_info = _check_binance_daily_quota(db, account.id)
        if quota_exceeded:
            logger.warning(
                f"[BINANCE] AI Trader '{account.name}' quota exceeded - "
                f"Decision recorded but NOT executed ({quota_info['used']}/{quota_info['limit']})"
            )
            # Save decision with executed=False and quota exceeded reason
            decision["_quota_exceeded"] = True
            decision["_quota_info"] = quota_info
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return

    # 4. Validate symbol
    if not symbol:
        logger.warning(f"[BINANCE] No symbol provided in decision for {account.name}")
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    # 4. Validate leverage range
    if leverage < 1 or leverage > max_leverage:
        logger.warning(
            f"[BINANCE] Invalid leverage {leverage}x from AI (max: {max_leverage}x), "
            f"using default {default_leverage}x"
        )
        leverage = default_leverage

    # 5. Get price
    price = prices.get(symbol, 0)
    if not price or price <= 0:
        logger.warning(f"[BINANCE] Invalid price for {symbol} for {account.name}")
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    if operation in ("buy", "sell"):
        from services.ai_review.orchestrator import review_and_apply

        review_result = review_and_apply(
            db,
            account=account,
            decision=decision,
            portfolio=portfolio,
            positions=positions,
            prices=prices,
            exchange="binance",
            environment=wallet.environment if wallet is not None else "paper",
            trigger_context=trigger_context,
            decision_kwargs=decision_kwargs,
        )
        if not review_result["allowed"]:
            logger.warning(
                "[BINANCE] AI review blocked %s %s for %s: %s",
                operation,
                symbol,
                account.name,
                review_result["reason"],
            )
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return

    # 5a. Mainnet signal validation gate (问题.md §1): testnet is the
    # validation sandbox; a signal may drive MAINNET orders only after its
    # settled forward record is big enough and net positive.
    if (
        operation in ("buy", "sell")
        and wallet is not None
        and wallet.environment == "mainnet"
        and (decision_kwargs or {}).get("signal_trigger_id")
    ):
        from services.signal_trigger_validation import signal_validation_gate

        gate = signal_validation_gate(db, trigger_context)
        if not gate["allowed"]:
            logger.warning(
                f"[BINANCE] Signal validation gate blocked {operation} {symbol} "
                f"for {account.name}: {gate['reason']}"
            )
            decision["_signal_validation_blocked"] = gate["reason"]
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return

    # 5b. Deterministic pre-trade risk guards (loss streak / exposure cap).
    # 2026-07-06 testnet: the LLM repeated one bearish thesis 5x (all losses)
    # and stacked same-direction exposure until margin monitors force-closed.
    if operation in ("buy", "sell"):
        from .risk_guards import check_pre_trade_guards

        guard = check_pre_trade_guards(
            db,
            account_id=account.id,
            symbol=symbol,
            operation=operation,
            positions=positions,
            total_equity=float(portfolio.get("total_assets") or 0),
        )
        if not guard["allowed"]:
            logger.warning(
                f"[BINANCE] Risk guard blocked {operation} {symbol} for {account.name}: {guard['reason']}"
            )
            decision["_risk_guard_blocked"] = guard["reason"]
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return

    order_result = None

    try:
        if operation == "buy":
            # 6. Validate target_portion
            if target_portion <= 0 or target_portion > 1:
                logger.warning(f"[BINANCE] Invalid target_portion {target_portion} from AI for {account.name}")
                save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                return

            # 7. Calculate quantity: margin * leverage / price
            margin = available_balance * target_portion
            order_value = margin * leverage
            quantity = round(order_value / price, 6)

            logger.info(
                f"[BINANCE] Position sizing for {symbol}: "
                f"margin=${margin:.2f} ({target_portion:.1%} of ${available_balance:.2f}), "
                f"leverage={leverage}x, position_value=${order_value:.2f}, quantity={quantity}"
            )

            # 8. Place order with TP/SL
            order_result = client.place_order_with_tpsl(
                db=db,
                symbol=symbol,
                is_buy=True,
                size=quantity,
                price=price,
                leverage=leverage,
                order_type="MARKET",
                reduce_only=False,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price
            )

        elif operation == "sell":
            # Validate target_portion
            if target_portion <= 0 or target_portion > 1:
                logger.warning(f"[BINANCE] Invalid target_portion {target_portion} from AI for {account.name}")
                save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                return

            # Calculate quantity
            margin = available_balance * target_portion
            order_value = margin * leverage
            quantity = round(order_value / price, 6)

            logger.info(
                f"[BINANCE] Position sizing for {symbol}: "
                f"margin=${margin:.2f} ({target_portion:.1%} of ${available_balance:.2f}), "
                f"leverage={leverage}x, position_value=${order_value:.2f}, quantity={quantity}"
            )

            # Place order with TP/SL
            order_result = client.place_order_with_tpsl(
                db=db,
                symbol=symbol,
                is_buy=False,
                size=quantity,
                price=price,
                leverage=leverage,
                order_type="MARKET",
                reduce_only=False,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price
            )

        elif operation == "close":
            # Close position
            result = client.close_position(symbol, cancel_tpsl=True)
            if result:
                logger.info(f"[BINANCE] Position closed: {symbol}")
                save_ai_decision(
                    db, account, decision, portfolio, executed=True,
                    hyperliquid_order_id=str(result.get("order_id")) if result.get("order_id") else None,
                    **decision_kwargs
                )
                # Save HyperliquidTrade record (consistent with Hyperliquid)
                try:
                    from database.snapshot_connection import SnapshotSessionLocal
                    from database.snapshot_models import HyperliquidTrade
                    from decimal import Decimal

                    snapshot_db = SnapshotSessionLocal()
                    try:
                        # Use Binance official fields, fallback to market price if 0
                        filled_qty = float(result.get('filled_qty', 0))
                        avg_price_val = float(result.get('avg_price', 0))
                        # For close, use filled_qty or position size from result
                        trade_qty = Decimal(str(filled_qty)) if filled_qty > 0 else Decimal('0')
                        trade_price = Decimal(str(avg_price_val)) if avg_price_val > 0 else Decimal(str(price))

                        trade_record = HyperliquidTrade(
                            account_id=account.id,
                            environment=wallet.environment if wallet else "mainnet",
                            wallet_address=f"binance_{account.id}",
                            symbol=symbol,
                            side="close",
                            quantity=trade_qty,
                            price=trade_price,
                            leverage=1,
                            order_id=str(result.get('order_id', '')),
                            order_status=result.get('status', 'filled'),
                            trade_value=trade_qty * trade_price,
                            fee=Decimal('0')
                        )
                        snapshot_db.add(trade_record)
                        snapshot_db.commit()
                        logger.info(f"[BINANCE] Close trade record saved for {account.name}")
                    finally:
                        snapshot_db.close()
                except Exception as trade_err:
                    logger.warning(f"Failed to save Binance close trade record: {trade_err}")
            else:
                logger.info(f"[BINANCE] No position to close for {symbol}")
                save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
            return

        # 9. Save decision with order IDs for attribution
        if order_result:
            status = order_result.get("status", "error")
            executed = status in ["filled", "resting"]

            save_ai_decision(
                db, account, decision, portfolio,
                executed=executed,
                hyperliquid_order_id=str(order_result.get("order_id")) if order_result.get("order_id") else None,
                tp_order_id=str(order_result.get("tp_order_id")) if order_result.get("tp_order_id") else None,
                sl_order_id=str(order_result.get("sl_order_id")) if order_result.get("sl_order_id") else None,
                **decision_kwargs
            )

            if executed:
                logger.info(
                    f"[BINANCE] {operation.upper()} order executed: {symbol} "
                    f"order_id={order_result.get('order_id')} "
                    f"tp_id={order_result.get('tp_order_id')} sl_id={order_result.get('sl_order_id')}"
                )
                # Save HyperliquidTrade record (consistent with Hyperliquid)
                try:
                    from database.snapshot_connection import SnapshotSessionLocal
                    from database.snapshot_models import HyperliquidTrade
                    from decimal import Decimal

                    snapshot_db = SnapshotSessionLocal()
                    try:
                        # Use Binance official fields, fallback to decision values if 0
                        filled_qty = float(order_result.get('filled_qty', 0))
                        avg_price = float(order_result.get('avg_price', 0))
                        # If Binance returns 0 (MARKET order not yet filled), use decision values
                        trade_qty = Decimal(str(filled_qty)) if filled_qty > 0 else Decimal(str(quantity))
                        trade_price = Decimal(str(avg_price)) if avg_price > 0 else Decimal(str(price))

                        trade_record = HyperliquidTrade(
                            account_id=account.id,
                            environment=wallet.environment if wallet else "mainnet",
                            wallet_address=f"binance_{account.id}",
                            symbol=symbol,
                            side=operation,
                            quantity=trade_qty,
                            price=trade_price,
                            leverage=leverage,
                            order_id=str(order_result.get('order_id', '')),
                            order_status=status,
                            trade_value=trade_qty * trade_price,
                            fee=Decimal('0')
                        )
                        snapshot_db.add(trade_record)
                        snapshot_db.commit()
                        logger.info(f"[BINANCE] Trade record saved for {account.name}")
                    finally:
                        snapshot_db.close()
                except Exception as trade_err:
                    logger.warning(f"Failed to save Binance trade record: {trade_err}")
            else:
                logger.warning(f"[BINANCE] {operation.upper()} order failed: {order_result}")

    except Exception as e:
        logger.error(f"[BINANCE] Error executing {operation} for {symbol}: {e}", exc_info=True)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
