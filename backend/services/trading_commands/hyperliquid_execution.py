"""Per-decision execution for Hyperliquid AI trading."""
import logging
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from services.ai_decision_service import save_ai_decision

from .helpers import _enforce_price_bounds
from .hyperliquid_close_execution import execute_close_order

logger = logging.getLogger(__name__)


def _execute_hyperliquid_decision(
    *,
    db,
    account,
    client,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    available_balance: float,
    environment: str,
    wallet_address: str,
    symbol_whitelist: Iterable[str],
    decision_kwargs: Dict[str, Any],
    trigger_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Validate and execute one Hyperliquid AI decision."""
    if not isinstance(decision, dict):
        logger.warning("Skipping malformed Hyperliquid decision for %s: %s", account.name, decision)
        return

    operation = decision.get("operation", "").lower()
    symbol = decision.get("symbol", "").upper()
    target_portion = float(decision.get("target_portion_of_balance", 0))
    leverage = int(decision.get("leverage", getattr(account, "default_leverage", 1)))
    max_price = decision.get("max_price")
    min_price = decision.get("min_price")
    reason = decision.get("reason", "No reason provided")

    logger.info(
        "AI decision for %s: %s %s (portion: %.2f%%, leverage: %sx, max_price: %s, min_price: %s) - %s",
        account.name,
        operation,
        symbol,
        target_portion * 100,
        leverage,
        max_price,
        min_price,
        reason,
    )

    if operation not in ["buy", "sell", "hold", "close"]:
        logger.warning("Invalid operation '%s' from AI for %s", operation, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    if operation == "hold":
        logger.info("AI decided to HOLD for %s - no action taken", account.name)
        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
        return

    if symbol not in symbol_whitelist:
        logger.warning("Symbol '%s' not in Hyperliquid watchlist for %s", symbol, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    from services.hyperliquid_environment import get_leverage_settings

    leverage_settings = get_leverage_settings(db, account.id, environment)
    max_leverage = leverage_settings["max_leverage"]
    default_leverage = leverage_settings["default_leverage"]
    if leverage < 1 or leverage > max_leverage:
        logger.warning(
            "Invalid leverage %sx from AI (max: %sx), using default %sx",
            leverage,
            max_leverage,
            default_leverage,
        )
        leverage = default_leverage

    if target_portion <= 0 or target_portion > 1:
        logger.warning("Invalid target_portion %s from AI for %s", target_portion, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    price = prices.get(symbol)
    if not price or price <= 0:
        logger.warning("Invalid price for %s for %s", symbol, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    should_cancel_orders = False
    if operation in ("buy", "sell"):
        from services.ai_review.orchestrator import review_and_apply

        review_result = review_and_apply(
            db,
            account=account,
            decision=decision,
            portfolio=portfolio,
            positions=positions,
            prices=prices,
            exchange="hyperliquid",
            environment=environment,
            trigger_context=trigger_context,
            decision_kwargs=decision_kwargs,
        )
        if not review_result["allowed"]:
            logger.warning(
                "AI review blocked %s %s for %s: %s",
                operation,
                symbol,
                account.name,
                review_result["reason"],
            )
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return

        # Deterministic pre-trade risk guards (loss streak / exposure cap) -
        # same hygiene as the Binance path; see risk_guards.py for the
        # 2026-07-06 testnet evidence that motivated them.
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
                "Risk guard blocked %s %s for %s: %s",
                operation, symbol, account.name, guard["reason"],
            )
            decision["_risk_guard_blocked"] = guard["reason"]
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return
        order_result = _execute_entry_order(
            db=db,
            account_name=account.name,
            client=client,
            decision=decision,
            symbol=symbol,
            operation=operation,
            price=price,
            target_portion=target_portion,
            leverage=leverage,
            available_balance=available_balance,
            environment=environment,
            max_price=max_price,
            min_price=min_price,
        )
    elif operation == "close":
        order_result, should_cancel_orders, handled = execute_close_order(
            db=db,
            account=account,
            client=client,
            decision=decision,
            portfolio=portfolio,
            positions=positions,
            prices=prices,
            environment=environment,
            symbol=symbol,
            target_portion=target_portion,
            min_price=min_price,
            decision_kwargs=decision_kwargs,
        )
        if handled:
            return
    else:
        return

    _handle_order_result(
        db=db,
        account=account,
        client=client,
        decision=decision,
        portfolio=portfolio,
        operation=operation,
        symbol=symbol,
        leverage=leverage,
        environment=environment,
        wallet_address=wallet_address,
        should_cancel_orders=should_cancel_orders,
        order_result=order_result,
        decision_kwargs=decision_kwargs,
    )


def _execute_entry_order(
    *,
    db,
    account_name: str,
    client,
    decision: Dict[str, Any],
    symbol: str,
    operation: str,
    price: float,
    target_portion: float,
    leverage: int,
    available_balance: float,
    environment: str,
    max_price: Any,
    min_price: Any,
) -> Dict[str, Any]:
    is_buy = operation == "buy"
    margin = available_balance * target_portion
    order_value = margin * leverage
    quantity = round(order_value / price, 6)

    logger.info(
        "Position sizing for %s: margin=$%.2f (%.1f%% of $%.2f), leverage=%sx, position_value=$%.2f, quantity=%s",
        symbol,
        margin,
        target_portion * 100,
        available_balance,
        leverage,
        order_value,
        quantity,
    )

    price_to_use = _resolve_entry_price(
        account_name,
        symbol,
        operation,
        price,
        max_price if is_buy else min_price,
    )
    take_profit_price = decision.get("take_profit_price")
    stop_loss_price = decision.get("stop_loss_price")
    time_in_force = decision.get("time_in_force", "Ioc")
    tp_execution = decision.get("tp_execution", "limit")
    sl_execution = decision.get("sl_execution", "limit")

    logger.info(
        "[HYPERLIQUID %s] Placing %s order: %s size=%s leverage=%sx TIF=%s TP=%s SL=%s",
        environment.upper(),
        operation.upper(),
        symbol,
        quantity,
        leverage,
        time_in_force,
        take_profit_price,
        stop_loss_price,
    )

    order_result = client.place_order_with_tpsl(
        db=db,
        symbol=symbol,
        is_buy=is_buy,
        size=quantity,
        price=price_to_use,
        leverage=leverage,
        time_in_force=time_in_force,
        reduce_only=False,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        tp_execution=tp_execution,
        sl_execution=sl_execution,
    )
    if not _should_retry_entry_as_gtc(order_result):
        return order_result

    logger.warning("IOC order failed for %s %s, retrying with GTC limit order", operation.upper(), symbol)
    return client.place_order_with_tpsl(
        db=db,
        symbol=symbol,
        is_buy=is_buy,
        size=quantity,
        price=price_to_use,
        leverage=leverage,
        time_in_force="Gtc",
        reduce_only=False,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        tp_execution=tp_execution,
        sl_execution=sl_execution,
    )


def _resolve_entry_price(
    account_name: str,
    symbol: str,
    operation: str,
    market_price: float,
    requested_price: Any,
) -> float:
    if requested_price is None:
        logger.warning(
            "AI compliance issue - %s %s missing %s. Using market price $%.2f.",
            operation.upper(),
            symbol,
            "max_price" if operation == "buy" else "min_price",
            market_price,
        )
        return market_price

    price_to_use, price_deviation_percent, _ = _enforce_price_bounds(
        symbol=symbol,
        account_name=account_name,
        operation=operation,
        current_price=market_price,
        requested_price=requested_price,
    )
    logger.info(
        "Using AI-provided %s for %s %s: market=$%.2f, order=$%.2f, deviation=%.2f%%",
        "max_price" if operation == "buy" else "min_price",
        operation.upper(),
        symbol,
        market_price,
        price_to_use,
        price_deviation_percent,
    )
    return price_to_use


def _should_retry_entry_as_gtc(order_result: Dict[str, Any]) -> bool:
    if not order_result or order_result.get("status") != "error":
        return False

    error_msg = order_result.get("error", "")
    return "could not immediately match" in error_msg.lower() or "no resting orders" in error_msg.lower()


def _handle_order_result(
    *,
    db,
    account,
    client,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    operation: str,
    symbol: str,
    leverage: int,
    environment: str,
    wallet_address: str,
    should_cancel_orders: bool,
    order_result: Dict[str, Any],
    decision_kwargs: Dict[str, Any],
) -> None:
    if not order_result:
        logger.error("No order result received for %s", account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    print(f"[DEBUG] {operation.upper()} order_result: {order_result}")
    order_status = order_result.get("status")
    order_id = order_result.get("order_id")

    if order_status in ("filled", "resting"):
        decision_kwargs["hyperliquid_order_id"] = order_result.get("order_id")
        decision_kwargs["tp_order_id"] = order_result.get("tp_order_id")
        decision_kwargs["sl_order_id"] = order_result.get("sl_order_id")

    if order_status == "filled":
        logger.info(
            "[HYPERLIQUID] Order executed successfully for %s: %s %s order_id=%s",
            account.name,
            operation.upper(),
            symbol,
            order_id,
        )
        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
        if operation == "close" and should_cancel_orders:
            _cancel_remaining_orders(db, client, symbol)
        _save_trade_record(account, order_result, operation, symbol, leverage, environment, wallet_address, order_id)
    elif order_status == "resting":
        logger.info(
            "[HYPERLIQUID] Order placed (resting) for %s: %s %s order_id=%s",
            account.name,
            operation.upper(),
            symbol,
            order_id,
        )
        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
    else:
        error_msg = order_result.get("error", "Unknown error")
        logger.error("[HYPERLIQUID] Order failed for %s: %s %s - %s", account.name, operation.upper(), symbol, error_msg)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)


def _cancel_remaining_orders(db, client, symbol: str) -> None:
    try:
        remaining_orders = client.get_open_orders(db, symbol=symbol)
        if not remaining_orders:
            return

        logger.info("[CLOSE %s] Position closed. Cancelling %s remaining orders.", symbol, len(remaining_orders))
        for order in remaining_orders:
            order_id = order.get("order_id")
            order_type = order.get("order_type", "Unknown")
            if not order_id:
                continue
            try:
                if client.cancel_order(db, order_id, symbol):
                    logger.info("[CLOSE %s] Cancelled %s order #%s", symbol, order_type, order_id)
            except Exception as cancel_err:
                logger.warning("[CLOSE %s] Failed to cancel order #%s: %s", symbol, order_id, cancel_err)
    except Exception as orders_err:
        logger.warning("[CLOSE %s] Failed to fetch remaining orders: %s", symbol, orders_err)


def _save_trade_record(
    account,
    order_result: Dict[str, Any],
    operation: str,
    symbol: str,
    leverage: int,
    environment: str,
    wallet_address: str,
    order_id: Any,
) -> None:
    try:
        from database.snapshot_connection import SnapshotSessionLocal
        from database.snapshot_models import HyperliquidTrade

        snapshot_db = SnapshotSessionLocal()
        try:
            trade_record = HyperliquidTrade(
                account_id=account.id,
                environment=environment,
                wallet_address=wallet_address,
                symbol=symbol,
                side=operation,
                quantity=Decimal(str(order_result.get("filled_amount", 0))),
                price=Decimal(str(order_result.get("average_price", 0))),
                leverage=leverage,
                order_id=order_id,
                order_status=order_result.get("status"),
                trade_value=Decimal(str(order_result.get("filled_amount", 0)))
                * Decimal(str(order_result.get("average_price", 0))),
                fee=Decimal(str(order_result.get("fee", 0))),
            )
            snapshot_db.add(trade_record)
            snapshot_db.commit()
            logger.info("[HYPERLIQUID] Trade record saved for %s", account.name)
        finally:
            snapshot_db.close()
    except Exception as trade_err:
        logger.warning("Failed to save Hyperliquid trade record: %s", trade_err)
