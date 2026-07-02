"""TP/SL trigger simulation helpers for backtests."""

from typing import Any, Dict, List

from .models import BacktestTradeRecord
from .virtual_account import VirtualAccount


class TpSlExecutionMixin:
    def check_tp_sl_triggers(
        self,
        account: VirtualAccount,
        prices: Dict[str, float],
        timestamp: int,
    ) -> List[BacktestTradeRecord]:
        """Check if any TP/SL orders should trigger at the current prices."""
        triggered_trades = []
        orders_to_remove = []

        for order in account.pending_orders:
            symbol = order.symbol
            if symbol not in prices:
                continue

            pos = account.get_position(symbol)
            if not pos:
                orders_to_remove.append(order.order_id)
                continue

            current_price = prices[symbol]
            should_trigger = False
            if order.order_type == "take_profit":
                if pos.side == "long" and current_price >= order.trigger_price:
                    should_trigger = True
                elif pos.side == "short" and current_price <= order.trigger_price:
                    should_trigger = True
            elif order.order_type == "stop_loss":
                if pos.side == "long" and current_price <= order.trigger_price:
                    should_trigger = True
                elif pos.side == "short" and current_price >= order.trigger_price:
                    should_trigger = True

            if should_trigger:
                close_side = "sell" if pos.side == "long" else "buy"
                executed_price, _ = self.calculate_execution_price(order.trigger_price, close_side)
                actual_close_size = min(order.size, pos.size)
                if actual_close_size <= 0:
                    orders_to_remove.append(order.order_id)
                    continue

                notional = actual_close_size * executed_price
                fee = self.calculate_fee(notional)
                pnl = account.partial_close_position(
                    symbol=symbol,
                    size=actual_close_size,
                    exit_price=executed_price,
                    fee=fee,
                    entry_price=order.entry_price,
                )

                if pnl is not None:
                    entry_notional = actual_close_size * order.entry_price
                    pnl_percent = (pnl / entry_notional * 100) if entry_notional > 0 else 0
                    exit_reason = "tp" if order.order_type == "take_profit" else "sl"
                    triggered_trades.append(BacktestTradeRecord(
                        timestamp=order.created_at,
                        trigger_type="",
                        symbol=symbol,
                        operation="close",
                        side=pos.side,
                        entry_price=order.entry_price,
                        size=actual_close_size,
                        leverage=pos.leverage,
                        exit_price=executed_price,
                        exit_timestamp=timestamp,
                        exit_reason=exit_reason,
                        pnl=pnl,
                        pnl_percent=pnl_percent,
                        fee=fee,
                        reason=f"{'Take Profit' if exit_reason == 'tp' else 'Stop Loss'} triggered",
                    ))

                orders_to_remove.append(order.order_id)

        for order_id in orders_to_remove:
            account.remove_pending_order(order_id)

        return triggered_trades

    def check_tp_sl_with_klines(
        self,
        account: VirtualAccount,
        klines: List[Dict[str, Any]],
        position_side: str,
        data_provider: Any,
    ) -> List[BacktestTradeRecord]:
        """Check TP/SL triggers using K-line high/low prices between triggers."""
        triggered_trades = []
        orders_to_remove = []

        for kline in klines:
            kline_time_ms = kline["timestamp"] * 1000
            high = kline["high"]
            low = kline["low"]

            for order in list(account.pending_orders):
                if order.order_id in orders_to_remove:
                    continue

                symbol = order.symbol
                pos = account.get_position(symbol)
                if not pos:
                    orders_to_remove.append(order.order_id)
                    continue

                should_trigger = False
                trigger_price = order.trigger_price
                if order.order_type == "take_profit":
                    if pos.side == "long" and high >= trigger_price:
                        should_trigger = True
                    elif pos.side == "short" and low <= trigger_price:
                        should_trigger = True
                elif order.order_type == "stop_loss":
                    if pos.side == "long" and low <= trigger_price:
                        should_trigger = True
                    elif pos.side == "short" and high >= trigger_price:
                        should_trigger = True

                if should_trigger:
                    close_side = "sell" if pos.side == "long" else "buy"
                    executed_price, _ = self.calculate_execution_price(trigger_price, close_side)
                    actual_close_size = min(order.size, pos.size)
                    if actual_close_size <= 0:
                        orders_to_remove.append(order.order_id)
                        continue

                    notional = actual_close_size * executed_price
                    fee = self.calculate_fee(notional)
                    pnl = account.partial_close_position(
                        symbol=symbol,
                        size=actual_close_size,
                        exit_price=executed_price,
                        fee=fee,
                        entry_price=order.entry_price,
                    )

                    if pnl is not None:
                        kline_prices = {symbol: kline["close"]}
                        for pos_symbol in account.positions:
                            if pos_symbol != symbol:
                                other_price = data_provider._get_price_at_time(pos_symbol, kline_time_ms)
                                if other_price:
                                    kline_prices[pos_symbol] = other_price
                        account.update_equity(kline_prices)

                        entry_notional = actual_close_size * order.entry_price
                        pnl_percent = (pnl / entry_notional * 100) if entry_notional > 0 else 0
                        exit_reason = "tp" if order.order_type == "take_profit" else "sl"
                        triggered_trades.append(BacktestTradeRecord(
                            timestamp=order.created_at,
                            trigger_type="",
                            symbol=symbol,
                            operation="close",
                            side=pos.side,
                            entry_price=order.entry_price,
                            size=actual_close_size,
                            leverage=pos.leverage,
                            exit_price=executed_price,
                            exit_timestamp=kline_time_ms,
                            exit_reason=exit_reason,
                            pnl=pnl,
                            pnl_percent=pnl_percent,
                            fee=fee,
                            equity_after=account.equity,
                            reason=f"{'Take Profit' if exit_reason == 'tp' else 'Stop Loss'} triggered",
                        ))

                    orders_to_remove.append(order.order_id)

        for order_id in orders_to_remove:
            account.remove_pending_order(order_id)

        return triggered_trades
