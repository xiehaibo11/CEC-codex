"""
Position close and TP/SL order orchestration for BinanceTradingClient.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BinanceTradingTpslMixin:
    """Position closing and entry-with-TP/SL methods."""

    def close_position(self, symbol: str, cancel_tpsl: bool = True) -> Optional[Dict[str, Any]]:
        """
        Close entire position for a symbol using market order.

        Args:
            symbol: Trading pair symbol
            cancel_tpsl: If True, also cancel associated TP/SL algo orders

        Returns:
            Order result if position exists, None if no position
        """
        positions = self.get_positions()
        position = next((p for p in positions if p["symbol"] == symbol.upper()), None)

        if not position or position["szi"] == 0:
            logger.info(f"[BINANCE] No position to close for {symbol}")
            return None

        # Determine side to close
        size = abs(position["szi"])
        side = "SELL" if position["szi"] > 0 else "BUY"

        # Place market order to close position
        result = self.place_order(
            symbol=symbol,
            side=side,
            quantity=size,
            order_type="MARKET",
            reduce_only=True,
        )

        # Cancel associated TP/SL algo orders
        if cancel_tpsl:
            try:
                algo_result = self.cancel_all_algo_orders(symbol)
                result["cancelled_algo_orders"] = algo_result
                logger.info(f"[BINANCE] Closed position and cancelled {algo_result['cancelled_count']} TP/SL orders for {symbol}")
            except Exception as e:
                logger.warning(f"[BINANCE] Position closed but failed to cancel TP/SL: {e}")
                result["cancelled_algo_orders"] = {"error": str(e)}

        return result

    def place_order_with_tpsl(
        self,
        db,
        symbol: str,
        is_buy: bool,
        size: float,
        price: float,
        leverage: int = 1,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        order_type: str = "MARKET",
        tp_execution: str = "market",  # Ignored for Binance (always market)
        sl_execution: str = "market",  # Ignored for Binance (always market)
    ) -> Dict[str, Any]:
        """
        Place order with take profit and stop loss (unified interface matching Hyperliquid).

        Args:
            db: Database session (for compatibility, not used in Binance)
            symbol: Asset symbol (e.g., "BTC")
            is_buy: True for long, False for short
            size: Order quantity
            price: Order price (used for LIMIT orders, ignored for MARKET)
            leverage: Position leverage
            time_in_force: Order time in force - "GTC", "IOC", "FOK", "GTX" or Hyperliquid style "Ioc", "Gtc"
            reduce_only: Only close existing positions
            take_profit_price: Optional take profit trigger price
            stop_loss_price: Optional stop loss trigger price
            order_type: "MARKET" or "LIMIT"
            tp_execution: Ignored for Binance (always uses TAKE_PROFIT_MARKET)
            sl_execution: Ignored for Binance (always uses STOP_MARKET)

        Returns:
            Dict with order results including TP/SL order IDs
        """
        # Normalize time_in_force from Hyperliquid style to Binance style
        tif_mapping = {"ioc": "IOC", "gtc": "GTC", "alo": "GTX"}
        time_in_force = tif_mapping.get(time_in_force.lower(), time_in_force.upper())

        # Validate parameters
        if leverage < 1:
            raise ValueError(f"Invalid leverage: {leverage}. Must be >= 1")
        if size <= 0:
            raise ValueError(f"Invalid size: {size}. Must be positive")
        if price <= 0 and order_type.upper() == "LIMIT":
            raise ValueError(f"Invalid price: {price}. Must be positive for LIMIT orders")

        # Validate time_in_force
        valid_tif = ["GTC", "IOC", "FOK", "GTX"]
        if time_in_force.upper() not in valid_tif:
            raise ValueError(f"Invalid time_in_force: {time_in_force}. Must be one of {valid_tif}")

        side = "BUY" if is_buy else "SELL"

        logger.info(
            f"[BINANCE] Placing order on {self.environment.upper()}: "
            f"{symbol} {side} size={size} price={price} "
            f"leverage={leverage}x TIF={time_in_force} TP={take_profit_price} SL={stop_loss_price}"
        )

        result = {
            "status": "error",
            "order_id": None,
            "tp_order_id": None,
            "sl_order_id": None,
            "filled_qty": 0.0,
            "avg_price": 0.0,
            "environment": self.environment,
            "errors": [],
        }

        try:
            # Place main order
            main_result = self.place_order(
                symbol=symbol,
                side=side,
                quantity=size,
                order_type=order_type,
                price=price if order_type.upper() == "LIMIT" else None,
                time_in_force=time_in_force if order_type.upper() == "LIMIT" else "GTC",
                reduce_only=reduce_only,
                leverage=leverage,
            )

            main_order_id = main_result.get("order_id")
            main_status = main_result.get("status")
            executed_qty = main_result.get("executed_qty", 0) or size

            result["order_id"] = main_order_id
            result["filled_qty"] = float(main_result.get("executed_qty", 0))
            result["avg_price"] = float(main_result.get("avg_price", 0))
            result["raw_main_order"] = main_result

            # Check if main order succeeded
            if main_status in ("FILLED", "NEW", "PARTIALLY_FILLED"):
                result["status"] = "filled" if main_status == "FILLED" else "resting"
                logger.info(f"[BINANCE] Main order succeeded: {main_order_id} status={main_status}")

                # Place TP/SL orders if main order succeeded and not reduce_only
                if not reduce_only:
                    close_side = "SELL" if is_buy else "BUY"

                    # Place Take Profit order
                    # tp_execution: "market" -> TAKE_PROFIT_MARKET, "limit" -> TAKE_PROFIT
                    if take_profit_price and take_profit_price > 0:
                        try:
                            tp_order_type = "TAKE_PROFIT" if tp_execution == "limit" else "TAKE_PROFIT_MARKET"
                            tp_result = self.place_stop_order(
                                symbol=symbol,
                                side=close_side,
                                quantity=executed_qty,
                                stop_price=take_profit_price,
                                order_type=tp_order_type,
                                reduce_only=True,
                                client_algo_id=f"TP_{main_order_id}" if main_order_id else None,
                            )
                            result["tp_order_id"] = tp_result.get("algo_id")
                            result["raw_tp_order"] = tp_result
                            logger.info(f"[BINANCE] TP order placed: algo_id={result['tp_order_id']} type={tp_order_type}")
                        except Exception as tp_err:
                            logger.error(f"[BINANCE] Failed to place TP order: {tp_err}")
                            result["errors"].append(f"TP order failed: {str(tp_err)}")

                    # Place Stop Loss order
                    # sl_execution: "market" -> STOP_MARKET, "limit" -> STOP
                    if stop_loss_price and stop_loss_price > 0:
                        try:
                            sl_order_type = "STOP" if sl_execution == "limit" else "STOP_MARKET"
                            sl_result = self.place_stop_order(
                                symbol=symbol,
                                side=close_side,
                                quantity=executed_qty,
                                stop_price=stop_loss_price,
                                order_type=sl_order_type,
                                reduce_only=True,
                                client_algo_id=f"SL_{main_order_id}" if main_order_id else None,
                            )
                            result["sl_order_id"] = sl_result.get("algo_id")
                            result["raw_sl_order"] = sl_result
                            logger.info(f"[BINANCE] SL order placed: algo_id={result['sl_order_id']} type={sl_order_type}")
                        except Exception as sl_err:
                            logger.error(f"[BINANCE] Failed to place SL order: {sl_err}")
                            result["errors"].append(f"SL order failed: {str(sl_err)}")
            else:
                result["status"] = "error"
                result["error"] = f"Main order failed with status: {main_status}"
                logger.warning(f"[BINANCE] Main order failed: {main_result}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"[BINANCE] place_order_with_tpsl failed: {e}", exc_info=True)

        return result
