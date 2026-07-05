"""HiBT perpetual futures order endpoints.

Mixed into :class:`services.hibt_trading_client.HibtTradingClient`. Holds the
signed order, batch-order and conditional (entrust) REST endpoints from the
official perpetual contract docs (https://apidoc.hibt.co/hibt-openapi-en).
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


class HibtOrderMixin:
    """Signed order/entrust REST endpoints; relies on ``_request`` and symbol
    helpers provided by the concrete client class."""

    def _build_open_payload(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        leverage: int = 1,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        custom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        order_type_upper = order_type.upper()
        payload: Dict[str, Any] = {
            "symbol": self.to_hibt_symbol(symbol),
            "type": 2 if order_type_upper == "MARKET" else 1,
            "side": 1 if side.upper() == "BUY" else 2,
            "leverage": int(leverage),
            "amount": str(quantity),
        }
        if custom_id:
            payload["customID"] = custom_id
        if order_type_upper == "LIMIT":
            if price is None:
                raise ValueError("Price required for HiBT limit order")
            payload["price"] = str(price)
        if take_profit_price is not None:
            payload["isSetSp"] = True
            payload["spPrice"] = str(take_profit_price)
            payload.setdefault("triggerType", 2)
        if stop_loss_price is not None:
            payload["isSetSl"] = True
            payload["slPrice"] = str(stop_loss_price)
            payload.setdefault("triggerType", 2)
        return payload

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        leverage: int = 1,
        reduce_only: bool = False,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        custom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if reduce_only:
            raise ValueError("HiBT reduce-only close requires close_position with a position ID")
        order_type_upper = order_type.upper()
        payload = self._build_open_payload(
            symbol,
            side,
            quantity,
            order_type=order_type,
            price=price,
            leverage=leverage,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            custom_id=custom_id,
        )
        data = self._request("POST", "/v2/order/open", payload, signed=True)
        return {
            "order_id": data.get("orderID") if isinstance(data, dict) else None,
            "status": "submitted",
            "symbol": self.to_display_symbol(symbol),
            "side": side.upper(),
            "type": order_type_upper,
            "quantity": float(quantity),
            "price": float(price or 0),
            "environment": self.environment,
            "raw_response": data,
        }

    def close_position(self, position_id: str, quantity: float, order_type: str = "MARKET", price: Optional[float] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "positionID": position_id,
            "amount": str(quantity),
            "type": 2 if order_type.upper() == "MARKET" else 1,
        }
        if order_type.upper() == "LIMIT":
            if price is None:
                raise ValueError("Price required for HiBT limit close")
            payload["price"] = str(price)
        data = self._request("POST", "/v2/order/close", payload, signed=True)
        return {"order_id": data.get("orderID") if isinstance(data, dict) else None, "status": "submitted", "raw_response": data}

    def cancel_order(self, symbol: str, order_id: str | None = None, custom_id: str | None = None, position_id: str | None = None) -> Any:
        payload = {
            "symbol": self.to_hibt_symbol(symbol),
            "orderID": order_id or "",
            "customID": custom_id or "",
            "positionID": position_id or "",
        }
        return self._request("POST", "/v2/order/cancel", payload, signed=True)

    def place_batch_orders(self, orders: list[Mapping[str, Any]]) -> Dict[str, Any]:
        """Batch open (``/v2/order/batchOpen``); returns success/fail maps keyed by customID."""
        items = [
            self._build_open_payload(
                order["symbol"],
                order["side"],
                order["quantity"],
                order_type=str(order.get("order_type", "MARKET")),
                price=order.get("price"),
                leverage=int(order.get("leverage", 1)),
                take_profit_price=order.get("take_profit_price"),
                stop_loss_price=order.get("stop_loss_price"),
                custom_id=order.get("custom_id"),
            )
            for order in orders
        ]
        data = self._request("POST", "/v2/order/batchOpen", {"items": items}, signed=True)
        return data if isinstance(data, dict) else {}

    def cancel_batch_orders(
        self,
        symbol: str,
        order_ids: list[str] | None = None,
        custom_ids: list[str] | None = None,
        position_ids: list[str] | None = None,
    ) -> Dict[str, Any]:
        """Batch cancel (``/v2/order/batchCancel``); exactly one ID list must be given."""
        provided = [ids for ids in (order_ids, custom_ids, position_ids) if ids]
        if len(provided) != 1:
            raise ValueError("HiBT batch cancel requires exactly one of order_ids, custom_ids or position_ids")
        payload: Dict[str, Any] = {"symbol": self.to_hibt_symbol(symbol)}
        if order_ids:
            payload["listOrderID"] = list(order_ids)
        if custom_ids:
            payload["listCustomID"] = list(custom_ids)
        if position_ids:
            payload["listPositionID"] = list(position_ids)
        data = self._request("POST", "/v2/order/batchCancel", payload, signed=True)
        return data if isinstance(data, dict) else {}

    def close_all_positions(self, symbol: str) -> list[str]:
        """Close every position of a symbol (``/v2/order/closeAll``); returns order IDs."""
        data = self._request("POST", "/v2/order/closeAll", {"symbol": self.to_hibt_symbol(symbol)}, signed=True)
        if isinstance(data, dict):
            ids = data.get("listOrderID")
            return list(ids) if isinstance(ids, list) else []
        return data if isinstance(data, list) else []

    def get_open_orders(
        self,
        symbol: str | None = None,
        order_id: str | None = None,
        custom_id: str | None = None,
        position_id: str | None = None,
    ) -> list[Dict[str, Any]]:
        """Unfinished orders (``/v2/order/unFinish``)."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = self.to_hibt_symbol(symbol)
        if order_id:
            params["orderID"] = order_id
        if custom_id:
            params["customID"] = custom_id
        if position_id:
            params["positionID"] = position_id
        data = self._request("GET", "/v2/order/unFinish", params, signed=True)
        return data if isinstance(data, list) else []

    def get_finished_order(
        self,
        symbol: str,
        order_id: str | None = None,
        custom_id: str | None = None,
        position_id: str | None = None,
    ) -> Any:
        """Completed order details (``/v2/order/finishedInfo``)."""
        params: Dict[str, Any] = {"symbol": self.to_hibt_symbol(symbol)}
        if order_id:
            params["orderID"] = order_id
        if custom_id:
            params["customID"] = custom_id
        if position_id:
            params["positionID"] = position_id
        return self._request("GET", "/v2/order/finishedInfo", params, signed=True)

    def get_order_history(
        self,
        symbol: str,
        start_time: int | None = None,
        end_time: int | None = None,
        page_index: int | None = None,
        page_size: int | None = None,
    ) -> Dict[str, Any]:
        """Completed orders (``/v2/order/finished``); start/end are SECONDS per docs, page_size<=50."""
        params: Dict[str, Any] = {"symbol": self.to_hibt_symbol(symbol)}
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)
        if page_index is not None:
            params["pageIndex"] = int(page_index)
        if page_size is not None:
            params["pageSize"] = int(page_size)
        data = self._request("GET", "/v2/order/finished", params, signed=True)
        return data if isinstance(data, dict) else {"total": 0, "page": 0, "data": data if isinstance(data, list) else []}

    def place_conditional_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        trigger_price: float,
        price: float,
        leverage: int = 1,
        trigger_type: int = 1,
        custom_id: Optional[str] = None,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        sp_sl_trigger_type: Optional[int] = None,
    ) -> Any:
        """Add a conditional/plan order (``/v2/entrust/add``); trigger_type 1=last, 2=index."""
        payload: Dict[str, Any] = {
            "symbol": self.to_hibt_symbol(symbol),
            "side": 1 if side.upper() == "BUY" else 2,
            "triggerType": int(trigger_type),
            "triggerPrice": str(trigger_price),
            "amount": str(quantity),
            "price": str(price),
            "leverage": int(leverage),
        }
        if custom_id:
            payload["customID"] = custom_id
        if sp_sl_trigger_type is not None:
            payload["spSlTriggerType"] = int(sp_sl_trigger_type)
        # Docs use capitalised IsSetSp/IsSetSl for the entrust endpoint.
        if take_profit_price is not None:
            payload["IsSetSp"] = True
            payload["spPrice"] = str(take_profit_price)
        if stop_loss_price is not None:
            payload["IsSetSl"] = True
            payload["slPrice"] = str(stop_loss_price)
        return self._request("POST", "/v2/entrust/add", payload, signed=True)

    def cancel_conditional_order(self, symbol: str, entrust_id: str | None = None, custom_id: str | None = None) -> Any:
        """Cancel a conditional order (``/v2/entrust/cancel``); one ID required."""
        if not entrust_id and not custom_id:
            raise ValueError("HiBT conditional cancel requires entrust_id or custom_id")
        params: Dict[str, Any] = {"symbol": self.to_hibt_symbol(symbol)}
        if entrust_id:
            params["entrustID"] = entrust_id
        if custom_id:
            params["customID"] = custom_id
        return self._request("POST", "/v2/entrust/cancel", params, signed=True)

    def get_open_conditional_orders(self, symbol: str) -> list[Dict[str, Any]]:
        """Unfinished conditional orders (``/v2/entrust/unFinish``)."""
        data = self._request("GET", "/v2/entrust/unFinish", {"symbol": self.to_hibt_symbol(symbol)}, signed=True)
        return data if isinstance(data, list) else []

    def get_conditional_order_history(self, symbol: str, page_index: int | None = None, page_size: int | None = None) -> Dict[str, Any]:
        """Completed conditional orders (``/v2/entrust/finished``); page_size<=50."""
        params: Dict[str, Any] = {"symbol": self.to_hibt_symbol(symbol)}
        if page_index is not None:
            params["pageIndex"] = int(page_index)
        if page_size is not None:
            params["pageSize"] = int(page_size)
        data = self._request("GET", "/v2/entrust/finished", params, signed=True)
        return data if isinstance(data, dict) else {"total": 0, "page": 0, "data": data if isinstance(data, list) else []}
