"""Binance Futures Testnet order probe helpers.

The probe places a small LIMIT order on Binance Futures Demo/Testnet and
immediately cancels it.  It is intended to prove that the app is calling the
real Binance Testnet order API instead of only doing local paper simulation.
"""

from __future__ import annotations

from typing import Any, Mapping


def run_binance_testnet_order_probe(
    *,
    wallet: Any,
    client: Any,
    symbol: str,
    side: str = "SELL",
    quantity: float = 0.001,
    leverage: int = 1,
    price_offset_pct: float = 5.0,
) -> dict[str, Any]:
    """Place a real Binance Futures Testnet limit order and cancel it.

    This helper deliberately rejects non-testnet wallets.  Backtests may remain
    local/historical, but this probe is exchange-backed and returns Binance
    order/cancel identifiers as proof of the external call.
    """

    environment = str(getattr(wallet, "environment", "") or "").lower()
    if environment != "testnet":
        raise ValueError("Binance order probe only supports testnet wallets")

    clean_symbol = str(symbol or "BTC").upper().replace("USDT", "")
    clean_side = str(side or "SELL").upper()
    if clean_side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")

    safe_quantity = float(quantity)
    if safe_quantity <= 0:
        raise ValueError("quantity must be positive")
    safe_leverage = max(1, min(int(leverage or 1), int(getattr(wallet, "max_leverage", 125) or 125)))
    offset = max(0.1, min(float(price_offset_pct or 5.0), 20.0))

    mark_price = float(client.get_mark_price(clean_symbol))
    if mark_price <= 0:
        raise ValueError("Unable to get Binance testnet mark price")

    multiplier = 1 + offset / 100 if clean_side == "SELL" else 1 - offset / 100
    limit_price = round(mark_price * multiplier, 1)
    if limit_price <= 0:
        raise ValueError("Calculated limit price is invalid")

    order_id: Any = None
    placed: Mapping[str, Any] = {}
    queried: Mapping[str, Any] = {}
    cancelled: Mapping[str, Any] = {}

    placed = client.place_order(
        symbol=clean_symbol,
        side=clean_side,
        quantity=safe_quantity,
        order_type="LIMIT",
        price=limit_price,
        time_in_force="GTC",
        reduce_only=False,
        leverage=safe_leverage,
    )
    order_id = placed.get("order_id") or placed.get("orderId")
    if not order_id:
        raise ValueError("Binance testnet order did not return order_id")

    try:
        queried = client.get_order(symbol=clean_symbol, order_id=order_id)
    finally:
        cancelled = client.cancel_order(symbol=clean_symbol, order_id=order_id)

    return {
        "success": True,
        "action": "binance_testnet_limit_order_then_cancel",
        "account_id": getattr(wallet, "account_id", None),
        "environment": environment,
        "base_url": getattr(client, "base_url", None),
        "symbol": clean_symbol,
        "side": clean_side,
        "quantity": safe_quantity,
        "leverage": safe_leverage,
        "mark_price": mark_price,
        "limit_price": limit_price,
        "order_id": order_id,
        "place_status": placed.get("status"),
        "query_status": queried.get("status"),
        "cancel_status": cancelled.get("status"),
    }
