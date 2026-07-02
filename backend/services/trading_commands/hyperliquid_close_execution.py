"""Close-position execution helpers for Hyperliquid AI trading."""
import logging
from typing import Any, Dict, List, Optional, Tuple

from services.ai_decision_service import save_ai_decision

from .helpers import _enforce_price_bounds

logger = logging.getLogger(__name__)


def execute_close_order(
    *,
    db,
    account,
    client,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    environment: str,
    symbol: str,
    target_portion: float,
    min_price: Optional[float],
    decision_kwargs: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], bool, bool]:
    """Execute a Hyperliquid close decision.

    Returns ``(order_result, should_cancel_orders, already_handled)``.
    ``already_handled`` is true when the function saved the AI decision itself.
    """
    should_cancel_orders = target_portion >= 1.0
    position_to_close = _find_position(positions, symbol)

    if position_to_close:
        position_size = abs(position_to_close.get("szi", 0))
        is_long = (position_to_close.get("szi", 0) or 0) > 0
    else:
        fallback = _resolve_missing_position(
            db,
            account,
            client,
            decision,
            portfolio,
            symbol,
            should_cancel_orders,
            decision_kwargs,
        )
        if fallback["handled"]:
            return None, should_cancel_orders, True
        position_size = fallback["position_size"]
        is_long = fallback["is_long"]

    if position_size <= 0:
        logger.warning("No position to close for %s (size=%s), skipping close operation", symbol, position_size)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return None, should_cancel_orders, True

    close_size = position_size * target_portion
    logger.info(
        "[HYPERLIQUID %s] Closing position: %s size=%s (closing %s)",
        environment.upper(),
        symbol,
        close_size,
        "long" if is_long else "short",
    )

    current_price = prices.get(symbol, 0)
    close_price = _resolve_close_price(
        account.name,
        decision,
        symbol,
        is_long,
        current_price,
        min_price,
    )

    order_result = _place_close_with_retries(
        db=db,
        client=client,
        account_name=account.name,
        symbol=symbol,
        is_long=is_long,
        close_size=close_size,
        close_price=close_price,
        current_price=current_price,
        prices=prices,
    )
    return order_result, should_cancel_orders, False


def _find_position(positions: List[Dict[str, Any]], symbol: str) -> Optional[Dict[str, Any]]:
    for pos in positions:
        if pos.get("coin") == symbol:
            return pos
    return None


def _resolve_missing_position(
    db,
    account,
    client,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    symbol: str,
    should_cancel_orders: bool,
    decision_kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    logger.warning(
        "Position %s not found in real-time positions list. Using portfolio snapshot data from AI prompt context.",
        symbol,
    )
    fallback_position = (portfolio.get("positions") or {}).get(symbol)
    if fallback_position:
        quantity = float(fallback_position.get("quantity") or 0)
        return {"handled": False, "position_size": abs(quantity), "is_long": quantity > 0}

    if should_cancel_orders and _cancel_pending_orders_without_position(
        db,
        account,
        client,
        decision,
        portfolio,
        symbol,
        decision_kwargs,
    ):
        return {"handled": True}

    logger.warning("Unable to locate Hyperliquid position data for %s; skipping close.", symbol)
    save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
    return {"handled": True}


def _cancel_pending_orders_without_position(
    db,
    account,
    client,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    symbol: str,
    decision_kwargs: Dict[str, Any],
) -> bool:
    try:
        pending_orders = client.get_open_orders(db, symbol=symbol)
        if not pending_orders:
            return False

        logger.info(
            "[CLOSE %s] No position found, but %s pending orders exist. Cancelling all orders as full exit.",
            symbol,
            len(pending_orders),
        )
        cancelled_count = 0
        for order in pending_orders:
            order_id = order.get("order_id")
            order_type = order.get("order_type", "Unknown")
            if not order_id:
                continue
            try:
                if client.cancel_order(db, order_id, symbol):
                    cancelled_count += 1
                    logger.info("[CLOSE %s] Cancelled %s order #%s", symbol, order_type, order_id)
            except Exception as cancel_err:
                logger.warning("[CLOSE %s] Failed to cancel order #%s: %s", symbol, order_id, cancel_err)

        if cancelled_count > 0:
            logger.info(
                "[CLOSE %s] Successfully cancelled %s/%s pending orders",
                symbol,
                cancelled_count,
                len(pending_orders),
            )
            save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
            return True
    except Exception as orders_err:
        logger.warning("[CLOSE %s] Failed to fetch pending orders: %s", symbol, orders_err)

    return False


def _resolve_close_price(
    account_name: str,
    decision: Dict[str, Any],
    symbol: str,
    is_long: bool,
    current_price: float,
    min_price: Optional[float],
) -> float:
    max_price_close = decision.get("max_price")
    if is_long:
        ai_close_price = min_price
        price_field_used = "min_price"
    else:
        ai_close_price = max_price_close if max_price_close is not None else min_price
        price_field_used = "max_price" if max_price_close is not None else "min_price"
        if max_price_close is None and min_price is not None:
            logger.warning(
                "AI compliance issue - CLOSE %s: short position provided min_price instead of max_price.",
                symbol,
            )

    if ai_close_price:
        close_price, price_deviation_percent, _ = _enforce_price_bounds(
            symbol=symbol,
            account_name=account_name,
            operation="close",
            current_price=current_price,
            requested_price=ai_close_price,
        )
        close_price, price_deviation_percent = _adjust_close_price_side(
            account_name,
            symbol,
            is_long,
            current_price,
            close_price,
            price_deviation_percent,
        )
        logger.info(
            "Using AI-provided %s for CLOSE %s: market=$%.2f, order=$%.2f, deviation=%.2f%%",
            price_field_used,
            symbol,
            current_price,
            close_price,
            price_deviation_percent,
        )
        return close_price

    fallback_multiplier = 0.995 if is_long else 1.005
    close_price, _, _ = _enforce_price_bounds(
        symbol=symbol,
        account_name=account_name,
        operation="close",
        current_price=current_price,
        requested_price=current_price * fallback_multiplier,
    )
    logger.warning(
        "AI compliance issue - CLOSE %s: missing %s. Using fallback price: market=$%.2f, order=$%.2f.",
        symbol,
        "min_price" if is_long else "max_price",
        current_price,
        close_price,
    )
    return close_price


def _adjust_close_price_side(
    account_name: str,
    symbol: str,
    is_long: bool,
    current_price: float,
    close_price: float,
    price_deviation_percent: float,
) -> Tuple[float, float]:
    if not is_long and close_price < current_price:
        requested_price = current_price * 1.005
    elif not is_long and close_price > current_price * 1.005:
        requested_price = current_price * 1.005
    elif is_long and close_price > current_price:
        requested_price = current_price * 0.995
    elif is_long and close_price < current_price * 0.995:
        requested_price = current_price * 0.995
    else:
        return close_price, price_deviation_percent

    return _enforce_price_bounds(
        symbol=symbol,
        account_name=account_name,
        operation="close",
        current_price=current_price,
        requested_price=requested_price,
    )[:2]


def _place_close_with_retries(
    *,
    db,
    client,
    account_name: str,
    symbol: str,
    is_long: bool,
    close_size: float,
    close_price: float,
    current_price: float,
    prices: Dict[str, float],
) -> Optional[Dict[str, Any]]:
    max_retries = 4
    retry_count = 0
    order_result = None
    price_multipliers = [0.996, 0.994, 0.992, 0.99] if is_long else [1.004, 1.006, 1.008, 1.01]

    while retry_count < max_retries and order_result is None:
        if retry_count == 0:
            attempt_price = close_price
        else:
            current_price_retry = prices.get(symbol, current_price)
            attempt_price = current_price_retry * price_multipliers[retry_count]
            attempt_price, _, _ = _enforce_price_bounds(
                symbol=symbol,
                account_name=account_name,
                operation="close",
                current_price=current_price_retry,
                requested_price=attempt_price,
            )
            logger.info(
                "[RETRY %s/%s] CLOSE %s: Adjusting price to $%.2f",
                retry_count,
                max_retries,
                symbol,
                attempt_price,
            )

        attempt_result = client.place_order_with_tpsl(
            db=db,
            symbol=symbol,
            is_buy=(not is_long),
            size=close_size,
            price=attempt_price,
            leverage=1,
            time_in_force="Ioc",
            reduce_only=True,
            take_profit_price=None,
            stop_loss_price=None,
        )

        if attempt_result and attempt_result.get("status") == "filled":
            if retry_count > 0:
                logger.info("CLOSE %s succeeded on retry %s with price $%.2f", symbol, retry_count, attempt_price)
            return attempt_result

        error_msg = attempt_result.get("error", "") if attempt_result else ""
        should_retry = (
            "could not immediately match" in error_msg.lower()
            or "no resting orders" in error_msg.lower()
        )
        if should_retry and retry_count < max_retries - 1:
            retry_count += 1
            logger.warning("CLOSE %s failed (attempt %s/%s): %s", symbol, retry_count, max_retries, error_msg)
        else:
            order_result = attempt_result
            break

    if order_result and order_result.get("status") == "filled":
        return order_result

    latest_price = prices.get(symbol, current_price) or current_price or close_price
    boundary_multiplier = 0.99 if is_long else 1.01
    fallback_price, _, _ = _enforce_price_bounds(
        symbol=symbol,
        account_name=account_name,
        operation="close",
        current_price=latest_price,
        requested_price=latest_price * boundary_multiplier,
    )
    logger.warning(
        "CLOSE %s entering fallback mode: placing reduce-only GTC at $%.2f",
        symbol,
        fallback_price,
    )
    return client.place_order_with_tpsl(
        db=db,
        symbol=symbol,
        is_buy=(not is_long),
        size=close_size,
        price=fallback_price,
        leverage=1,
        time_in_force="Gtc",
        reduce_only=True,
        take_profit_price=None,
        stop_loss_price=None,
    )
