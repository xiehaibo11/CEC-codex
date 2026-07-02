"""
Open order read/format helpers for BinanceTradingClient.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional


class BinanceTradingOrderViewsMixin:
    """Unified order list formatting methods."""

    def get_open_orders(self, db=None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders including Algo orders (TP/SL), optionally filtered by symbol.

        Args:
            db: Database session (unused, for Hyperliquid API compatibility)
            symbol: Optional symbol to filter orders

        Returns:
            List of order dicts with unified format matching Hyperliquid:
            - order_id, symbol, side, direction, order_type, size, price
            - trigger_price, reduce_only, is_trigger, trigger_condition
        """
        params = {}
        if symbol:
            params["symbol"] = self._to_binance_symbol(symbol)

        # Get regular orders
        regular_orders = self._request("GET", "/fapi/v1/openOrders", params, signed=True)

        # Get algo orders (TP/SL)
        algo_result = self._request("GET", "/fapi/v1/openAlgoOrders", params, signed=True)
        algo_orders = algo_result.get("orders", []) if isinstance(algo_result, dict) else algo_result

        # Convert to unified format
        orders = []

        # Process regular orders
        for o in regular_orders:
            sym = o.get("symbol", "")
            if sym.endswith("USDT"):
                sym = sym[:-4]
            side_raw = o.get("side", "").upper()
            reduce_only = o.get("reduceOnly", False)
            side = "Buy" if side_raw == "BUY" else "Sell"
            if side == "Buy":
                direction = "Close Short" if reduce_only else "Open Long"
            else:
                direction = "Close Long" if reduce_only else "Open Short"

            orders.append({
                "order_id": o.get("orderId"),
                "symbol": sym,
                "side": side,
                "direction": direction,
                "order_type": o.get("type", "LIMIT"),
                "size": float(o.get("origQty", 0)),
                "price": float(o.get("price", 0)),
                "trigger_price": float(o.get("stopPrice", 0)) if o.get("stopPrice") else None,
                "reduce_only": reduce_only,
                "is_trigger": o.get("type", "").startswith("STOP") or o.get("type", "").startswith("TAKE"),
                "trigger_condition": None,
                "timestamp": o.get("time", 0),
            })

        # Process algo orders (TP/SL)
        for o in algo_orders:
            sym = o.get("symbol", "")
            if sym.endswith("USDT"):
                sym = sym[:-4]
            side_raw = o.get("side", "").upper()
            side = "Buy" if side_raw == "BUY" else "Sell"
            reduce_only = o.get("reduceOnly", False)
            # Determine direction: Buy+reduceOnly=Close Short (buying to close short position)
            # Sell+reduceOnly=Close Long (selling to close long position)
            if side == "Buy":
                direction = "Close Short" if reduce_only else "Open Long"
            else:
                direction = "Close Long" if reduce_only else "Open Short"

            # Determine order type from orderType field (TAKE_PROFIT/STOP)
            order_type_raw = o.get("orderType", "")
            if order_type_raw == "TAKE_PROFIT":
                order_type = "Take Profit"
            elif order_type_raw == "STOP":
                order_type = "Stop Loss"
            else:
                order_type = order_type_raw or o.get("algoType", "CONDITIONAL")

            trigger_price = float(o.get("triggerPrice", 0)) if o.get("triggerPrice") else None
            # TP triggers when price reaches target (<=), SL triggers when price hits stop (>=)
            if trigger_price:
                if order_type_raw == "TAKE_PROFIT":
                    trigger_cond = f"Mark Price <= {trigger_price}"
                else:
                    trigger_cond = f"Mark Price >= {trigger_price}"
            else:
                trigger_cond = None

            orders.append({
                "order_id": o.get("algoId"),
                "symbol": sym,
                "side": side,
                "direction": direction,
                "order_type": order_type,
                "size": float(o.get("quantity", 0)),  # Algo orders use 'quantity' not 'origQty'
                "price": float(o.get("price", 0)),
                "trigger_price": trigger_price,
                "reduce_only": reduce_only,
                "is_trigger": True,
                "trigger_condition": trigger_cond,
                "timestamp": o.get("createTime", 0),  # Algo orders use 'createTime'
            })

        return orders

    def get_open_orders_formatted(self, db=None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get open orders in unified format (compatible with HyperliquidTradingClient).

        Returns list of dicts with fields:
            order_id, symbol, side, direction, order_type, size, price,
            order_value, reduce_only, trigger_condition, trigger_price, order_time

        Note: get_open_orders() now returns unified format including Algo orders (TP/SL),
        so this method simply delegates to it and adds order_value/order_time fields.
        """
        orders = self.get_open_orders(db, symbol)

        # Add order_value and order_time fields for compatibility
        for o in orders:
            price = float(o.get("price", 0))
            size = float(o.get("size", 0))
            o["order_value"] = price * size
            o["original_size"] = size
            # Convert timestamp to order_time string
            ts = o.get("timestamp", 0)
            o["order_time"] = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A"

        return orders
