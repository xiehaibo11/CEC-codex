"""Hyperliquid order read helpers."""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.exchanges.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)


class HyperliquidOrderReadsMixin:
    """Order and TP/SL read helpers for Hyperliquid clients."""

    def query_order_by_oid(self, db: Session, order_id: int) -> Optional[Dict[str, Any]]:
        self._validate_environment(db)

        try:
            logger.debug(f"Querying order {order_id} for wallet {self.query_address}")
            return self.sdk_info.query_order_by_oid(self.query_address, order_id)
        except Exception as err:
            logger.warning(f"Failed to query order {order_id}: {err}")
            return None

    def get_order_trigger_time(self, db: Session, order_id: int) -> Optional[datetime]:
        result = self.query_order_by_oid(db, order_id)
        if not result:
            return None

        status_timestamp = (result.get("order") or {}).get("statusTimestamp")
        if not status_timestamp:
            return None

        try:
            return datetime.utcfromtimestamp(status_timestamp / 1000)
        except Exception as err:
            logger.warning(f"Failed to parse statusTimestamp {status_timestamp}: {err}")
            return None

    def get_open_orders(self, db: Session, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        self._validate_environment(db)

        try:
            logger.info(f"Fetching open orders for wallet {self.query_address} on {self.environment}")
            raw_orders = self._fetch_frontend_open_orders_with_hip3()
            orders = [_format_open_order(order) for order in raw_orders]
            orders.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

            if symbol:
                internal_symbol = SymbolMapper.to_internal(symbol, "hyperliquid")
                orders = [order for order in orders if order.get("symbol") == internal_symbol]
                logger.debug(f"Filtered to {len(orders)} orders for symbol {symbol}")

            logger.info(f"Found {len(orders)} open orders")
            self._record_exchange_action(
                action_type="fetch_open_orders",
                status="success",
                symbol=symbol,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "environment": self.environment,
                    "symbol_filter": symbol,
                },
                response_payload=None,
            )
            return orders
        except Exception as err:
            self._record_exchange_action(
                action_type="fetch_open_orders",
                status="error",
                symbol=symbol,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "environment": self.environment,
                    "symbol_filter": symbol,
                },
                response_payload=None,
                error_message=str(err),
            )
            logger.error(f"Failed to get open orders: {err}", exc_info=True)
            return []

    def _get_open_orders_raw(self, db: Session, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        self._validate_environment(db)

        try:
            logger.info(f"Fetching raw open orders for wallet {self.query_address} on {self.environment}")
            open_orders = self._fetch_frontend_open_orders_with_hip3()
            logger.debug(f"Retrieved {len(open_orders)} open orders for wallet {self.query_address}")

            if symbol:
                internal_symbol = SymbolMapper.to_internal(symbol, "hyperliquid")
                open_orders = [
                    order
                    for order in open_orders
                    if SymbolMapper.to_internal(order.get("coin", ""), "hyperliquid") == internal_symbol
                ]
                logger.debug(f"Filtered to {len(open_orders)} orders for symbol {symbol}")

            self._record_exchange_action(
                action_type="fetch_open_orders_raw",
                status="success",
                symbol=symbol,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "symbol_filter": symbol,
                },
                response_payload=None,
            )
            return open_orders
        except Exception as err:
            self._record_exchange_action(
                action_type="fetch_open_orders_raw",
                status="error",
                symbol=symbol,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "symbol_filter": symbol,
                },
                error_message=str(err),
            )
            logger.error(f"Failed to get raw open orders: {err}", exc_info=True)
            raise

    def get_tpsl_orders(self, db: Session, symbol: str) -> Dict[str, Optional[Dict[str, Any]]]:
        open_orders = self._get_open_orders_raw(db, symbol)

        import sys

        print(f"[TPSL DEBUG] {symbol} - Found {len(open_orders)} open orders", file=sys.stderr, flush=True)
        logger.info(f"[TPSL DEBUG] {symbol} - Found {len(open_orders)} open orders")
        for index, order in enumerate(open_orders):
            print(f"[TPSL DEBUG] Order {index}: {order}", file=sys.stderr, flush=True)
            logger.info(f"[TPSL DEBUG] Order {index}: {order}")

        all_tp_orders = []
        all_sl_orders = []
        for order in open_orders:
            tpsl_type, trigger_price = _detect_tpsl_order(order)
            if not tpsl_type or not trigger_price:
                continue

            order_dict = {
                "oid": order.get("oid"),
                "trigger_price": trigger_price,
                "limit_price": float(order.get("limitPx", 0)),
                "size": float(order.get("sz", 0)),
                "side": order.get("side"),
                "reduce_only": order.get("reduceOnly", True),
                "timestamp": order.get("timestamp", 0),
            }
            if tpsl_type == "tp":
                all_tp_orders.append(order_dict)
                logger.info(f"[TPSL DEBUG] Identified TP order: {order_dict}")
            elif tpsl_type == "sl":
                all_sl_orders.append(order_dict)
                logger.info(f"[TPSL DEBUG] Identified SL order: {order_dict}")

        tp_order = all_tp_orders[0] if all_tp_orders else None
        sl_order = all_sl_orders[0] if all_sl_orders else None
        logger.info(f"[TPSL] {symbol} - Found {len(all_tp_orders)} TP orders, {len(all_sl_orders)} SL orders")
        logger.info(f"[TPSL] {symbol} - Primary TP={tp_order}, Primary SL={sl_order}")
        return {
            "tp": tp_order,
            "sl": sl_order,
            "all_tp_orders": all_tp_orders,
            "all_sl_orders": all_sl_orders,
        }


def _format_open_order(order: Dict[str, Any]) -> Dict[str, Any]:
    timestamp_ms = order.get("timestamp", 0)
    utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    side_raw = order.get("side", "")
    reduce_only = order.get("reduceOnly", False)

    if side_raw == "B":
        side = "Buy"
        direction = "Close Short" if reduce_only else "Open Long"
    else:
        side = "Sell"
        direction = "Close Long" if reduce_only else "Open Short"

    size = float(order.get("sz", 0))
    price = float(order.get("limitPx", 0))
    trigger_condition = order.get("triggerCondition", "")
    trigger_price = order.get("triggerPx")

    return {
        "order_id": order.get("oid"),
        "symbol": SymbolMapper.to_internal(order.get("coin", ""), "hyperliquid"),
        "side": side,
        "direction": direction,
        "order_type": order.get("orderType", "Limit"),
        "size": size,
        "original_size": float(order.get("origSz", 0)),
        "price": price,
        "order_value": size * price,
        "reduce_only": reduce_only,
        "is_trigger": order.get("isTrigger", False),
        "trigger_condition": trigger_condition if trigger_condition else None,
        "trigger_price": float(trigger_price) if trigger_price else None,
        "is_position_tpsl": order.get("isPositionTpsl", False),
        "tif": order.get("tif"),
        "order_time": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "timestamp": timestamp_ms,
    }


def _detect_tpsl_order(order: Dict[str, Any]) -> tuple[Optional[str], Optional[float]]:
    order_type = order.get("orderType", {})
    is_trigger = order.get("isTrigger", False)
    trigger_px = order.get("triggerPx")
    trigger_condition = order.get("triggerCondition", "")
    logger.debug(f"[TPSL DEBUG] Order type: {order_type}, type={type(order_type)}, isTrigger={is_trigger}")

    if isinstance(order_type, dict) and "trigger" in order_type:
        trigger_info = order_type.get("trigger", {})
        trigger_price = float(trigger_info.get("triggerPx", 0))
        tpsl_type = trigger_info.get("tpsl")
        logger.info(f"[TPSL DEBUG] Found dict trigger order: tpsl={tpsl_type}, trigger_price={trigger_price}")
        return tpsl_type, trigger_price

    if isinstance(order_type, str) and is_trigger:
        tpsl_type = None
        order_type_lower = order_type.lower()
        if "take profit" in order_type_lower:
            tpsl_type = "tp"
        elif "stop" in order_type_lower and "limit" in order_type_lower:
            tpsl_type = "sl"
        trigger_price = _parse_trigger_price(trigger_px)
        logger.info(
            f"[TPSL DEBUG] Found string trigger order: orderType='{order_type}', "
            f"tpsl={tpsl_type}, trigger_price={trigger_price}"
        )
        return tpsl_type, trigger_price

    if is_trigger and trigger_condition:
        tpsl_type = None
        if "above" in trigger_condition.lower():
            tpsl_type = "tp"
        elif "below" in trigger_condition.lower():
            tpsl_type = "sl"
        trigger_price = _parse_trigger_price(trigger_px)
        logger.info(
            f"[TPSL DEBUG] Found trigger by condition: condition='{trigger_condition}', "
            f"tpsl={tpsl_type}, trigger_price={trigger_price}"
        )
        return tpsl_type, trigger_price

    return None, None


def _parse_trigger_price(trigger_px: Any) -> float:
    if not trigger_px:
        return 0
    try:
        return float(trigger_px)
    except (ValueError, TypeError):
        return 0
