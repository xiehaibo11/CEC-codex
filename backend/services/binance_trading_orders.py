"""
Order methods for BinanceTradingClient.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BinanceTradingOrdersMixin:
    """Leverage, regular order, algo order, and order query methods."""

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Set leverage for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTC' or 'BTCUSDT')
            leverage: Target leverage (1-125, depends on symbol)

        Returns:
            Dict with leverage and maxNotionalValue
        """
        binance_symbol = self._to_binance_symbol(symbol)
        params = {
            "symbol": binance_symbol,
            "leverage": leverage,
        }

        result = self._request("POST", "/fapi/v1/leverage", params, signed=True)
        logger.info(f"[BINANCE] Set leverage for {binance_symbol}: {leverage}x")
        return result

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        leverage: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Place an order on Binance Futures.

        Args:
            symbol: Trading pair (e.g., 'BTC')
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            order_type: 'MARKET' or 'LIMIT'
            price: Limit price (required for LIMIT orders)
            time_in_force: 'GTC', 'IOC', 'FOK', 'GTX'
            reduce_only: Only reduce position
            leverage: Set leverage before order (optional)

        Returns:
            Order result dict with orderId, status, etc.
        """
        binance_symbol = self._to_binance_symbol(symbol)

        # Set leverage if specified (skip for close/reduce_only orders)
        if leverage and not reduce_only:
            self.set_leverage(symbol, leverage)

        # Get precision for rounding
        precision = self._get_precision(binance_symbol)
        rounded_qty = self._round_quantity(quantity, precision["step_size"])

        # Validate minimum quantity
        if rounded_qty < precision["min_qty"]:
            raise ValueError(
                f"Quantity {rounded_qty} below minimum {precision['min_qty']} for {binance_symbol}"
            )

        # Build order params
        params = {
            "symbol": binance_symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(rounded_qty),
            # Add broker ID prefix for commission tracking
            "newClientOrderId": f"x-{self.broker_id}-{self._get_timestamp()}",
        }

        if reduce_only:
            params["reduceOnly"] = "true"

        if order_type.upper() == "LIMIT":
            if price is None:
                raise ValueError("Price required for LIMIT orders")
            rounded_price = self._round_price(price, precision["tick_size"])
            params["price"] = str(rounded_price)
            params["timeInForce"] = time_in_force

        try:
            result = self._request("POST", "/fapi/v1/order", params, signed=True)
        except Exception as e:
            error_str = str(e)
            if "-4061" in error_str:
                raise Exception(
                    "Position mode mismatch: Your Binance account uses Hedge Mode (dual position). "
                    "Please switch to One-way Mode: Binance App → Futures → Settings → Position Mode → One-way Mode"
                )
            raise

        logger.info(
            f"[BINANCE] Order placed: {side} {rounded_qty} {binance_symbol} "
            f"@ {order_type} - Status: {result.get('status')}"
        )

        return {
            "order_id": result.get("orderId"),
            "client_order_id": result.get("clientOrderId"),
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": float(rounded_qty),
            "price": float(result.get("price", 0)),
            "avg_price": float(result.get("avgPrice", 0)),
            "executed_qty": float(result.get("executedQty", 0)),
            "status": result.get("status"),
            "time_in_force": result.get("timeInForce"),
            "reduce_only": result.get("reduceOnly", False),
            "environment": self.environment,
            "raw_response": result,
        }

    def place_stop_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        order_type: str = "STOP_MARKET",
        reduce_only: bool = True,
        working_type: str = "MARK_PRICE",
        client_algo_id: Optional[str] = None,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a stop-loss or take-profit order using Algo Order API.

        Since 2025-12-09, Binance migrated conditional orders to Algo Service.
        This method uses /fapi/v1/algoOrder endpoint.
        """
        binance_symbol = self._to_binance_symbol(symbol)
        precision = self._get_precision(binance_symbol)

        rounded_qty = self._round_quantity(quantity, precision["step_size"])
        rounded_stop = self._round_price(stop_price, precision["tick_size"])

        params = {
            "symbol": binance_symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "algoType": "CONDITIONAL",
            "quantity": str(rounded_qty),
            "triggerPrice": str(rounded_stop),
            "workingType": working_type,
            "timeInForce": "GTE_GTC",
        }

        # For limit-type orders (STOP, TAKE_PROFIT), price is required
        # Default to trigger price if not specified (方案B: price = triggerPrice)
        if order_type.upper() in ("STOP", "TAKE_PROFIT"):
            limit_price = price if price else stop_price
            rounded_price = self._round_price(limit_price, precision["tick_size"])
            params["price"] = str(rounded_price)

        if client_algo_id:
            params["clientAlgoId"] = client_algo_id

        if reduce_only:
            params["reduceOnly"] = "true"

        result = self._request("POST", "/fapi/v1/algoOrder", params, signed=True)

        logger.info(
            f"[BINANCE] Algo order placed: {order_type} {side} {rounded_qty} "
            f"{binance_symbol} trigger@{rounded_stop} algoId={result.get('algoId')}"
        )

        return {
            "algo_id": result.get("algoId"),
            "client_algo_id": result.get("clientAlgoId"),
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": float(rounded_qty),
            "trigger_price": float(rounded_stop),
            "status": result.get("algoStatus"),
            "working_type": working_type,
            "reduce_only": reduce_only,
            "environment": self.environment,
            "raw_response": result,
        }

    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cancel an open order.

        Args:
            symbol: Trading pair
            order_id: Binance order ID
            client_order_id: Client order ID (alternative to order_id)

        Returns:
            Cancelled order info
        """
        binance_symbol = self._to_binance_symbol(symbol)
        params = {"symbol": binance_symbol}

        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        else:
            raise ValueError("Either order_id or client_order_id required")

        result = self._request("DELETE", "/fapi/v1/order", params, signed=True)
        logger.info(f"[BINANCE] Order cancelled: {order_id or client_order_id}")
        return result

    def cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel all open orders for a symbol."""
        binance_symbol = self._to_binance_symbol(symbol)
        result = self._request(
            "DELETE",
            "/fapi/v1/allOpenOrders",
            {"symbol": binance_symbol},
            signed=True,
        )
        logger.info(f"[BINANCE] All orders cancelled for {binance_symbol}")
        return result

    def get_open_algo_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open Algo orders (TP/SL conditional orders).

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open algo orders
        """
        params = {}
        if symbol:
            params["symbol"] = self._to_binance_symbol(symbol)

        result = self._request("GET", "/fapi/v1/openAlgoOrders", params, signed=True)
        return result.get("orders", []) if isinstance(result, dict) else result

    def cancel_algo_order(self, symbol: str, algo_id: int) -> Dict[str, Any]:
        """
        Cancel a specific Algo order.

        Args:
            symbol: Trading pair
            algo_id: Algo order ID

        Returns:
            Cancellation result
        """
        binance_symbol = self._to_binance_symbol(symbol)
        params = {
            "symbol": binance_symbol,
            "algoId": algo_id,
        }
        result = self._request("DELETE", "/fapi/v1/algoOrder", params, signed=True)
        logger.info(f"[BINANCE] Algo order {algo_id} cancelled for {binance_symbol}")
        return result

    def cancel_all_algo_orders(self, symbol: str) -> Dict[str, Any]:
        """
        Cancel all open Algo orders (TP/SL) for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            Dict with cancelled count and details
        """
        binance_symbol = self._to_binance_symbol(symbol)
        algo_orders = self.get_open_algo_orders(symbol)

        cancelled = []
        errors = []

        for order in algo_orders:
            algo_id = order.get("algoId")
            if algo_id:
                try:
                    self.cancel_algo_order(symbol, algo_id)
                    cancelled.append(algo_id)
                except Exception as e:
                    logger.warning(f"[BINANCE] Failed to cancel algo order {algo_id}: {e}")
                    errors.append({"algo_id": algo_id, "error": str(e)})

        logger.info(f"[BINANCE] Cancelled {len(cancelled)} algo orders for {binance_symbol}")
        return {
            "symbol": symbol,
            "cancelled_count": len(cancelled),
            "cancelled_ids": cancelled,
            "errors": errors,
        }

    def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query a specific order by ID."""
        binance_symbol = self._to_binance_symbol(symbol)
        params = {"symbol": binance_symbol}

        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        else:
            raise ValueError("Either order_id or client_order_id required")

        return self._request("GET", "/fapi/v1/order", params, signed=True)

    def get_mark_price(self, symbol: str) -> float:
        """Get current mark price for a symbol."""
        binance_symbol = self._to_binance_symbol(symbol)
        result = self._request("GET", "/fapi/v1/premiumIndex", {"symbol": binance_symbol})
        return float(result.get("markPrice", 0))
