"""WebSocket subscription management and message ingest for market flow data."""

import time
import logging
from decimal import Decimal
from typing import List

from services.exchanges.symbol_mapper import SymbolMapper

from services.market_flow_collector.constants import TradeBuffer

logger = logging.getLogger(__name__)


class MarketFlowIngestMixin:
    """Subscription lifecycle and inbound WebSocket message handling."""

    def refresh_subscriptions(self, new_symbols: List[str]):
        """Update subscriptions when watchlist changes"""
        if not self.running:
            return

        current = set(self.subscribed_symbols)
        new = set(new_symbols)

        # Unsubscribe removed symbols
        for symbol in current - new:
            self._unsubscribe_symbol(symbol)

        # Subscribe new symbols
        for symbol in new - current:
            self._subscribe_symbol(symbol)

    def _get_original_coin_name(self, symbol: str) -> str:
        """Get the original coin name from Hyperliquid SDK (case-sensitive).

        Hyperliquid uses mixed-case names like 'kSHIB', 'kPEPE', but our watchlist
        stores uppercase versions. This method finds the original name.
        """
        if not self.info:
            return symbol

        # Try exact match first
        if symbol in self.info.name_to_coin:
            return symbol

        # Try case-insensitive match
        symbol_upper = symbol.upper()
        for coin in self.info.name_to_coin:
            if coin.upper() == symbol_upper:
                return coin

        return symbol

    def _subscribe_symbol(self, symbol: str):
        """Subscribe to all data streams for a symbol"""
        if not self.info:
            return

        # Convert to original Hyperliquid coin name (e.g., KSHIB -> kSHIB, GOLD -> xyz:GOLD)
        exchange_symbol = SymbolMapper.to_exchange(symbol, "hyperliquid")
        coin = self._get_original_coin_name(exchange_symbol)

        try:
            # Initialize buffer (use original symbol for internal tracking)
            self.trade_buffers[symbol] = TradeBuffer()
            self.large_order_tracker.ensure_symbols([symbol])

            # Subscribe to trades
            trades_id = self.info.subscribe(
                {"type": "trades", "coin": coin},
                lambda msg, s=symbol: self._on_trades(s, msg)
            )
            self.subscription_ids[symbol]["trades"] = trades_id

            # Subscribe to L2 orderbook
            l2_id = self.info.subscribe(
                {"type": "l2Book", "coin": coin},
                lambda msg, s=symbol: self._on_l2book(s, msg)
            )
            self.subscription_ids[symbol]["l2Book"] = l2_id

            # Subscribe to asset context (OI, funding, etc.)
            ctx_id = self.info.subscribe(
                {"type": "activeAssetCtx", "coin": coin},
                lambda msg, s=symbol: self._on_asset_ctx(s, msg)
            )
            self.subscription_ids[symbol]["activeAssetCtx"] = ctx_id

            self.subscribed_symbols.append(symbol)
            logger.info(f"Subscribed to market flow data for {symbol} (coin: {coin})")

        except Exception as e:
            logger.error(f"Failed to subscribe {symbol}: {e}")

    def _unsubscribe_symbol(self, symbol: str):
        """Unsubscribe from all data streams for a symbol"""
        if not self.info or symbol not in self.subscription_ids:
            return

        # Convert to original Hyperliquid coin name
        exchange_symbol = SymbolMapper.to_exchange(symbol, "hyperliquid")
        coin = self._get_original_coin_name(exchange_symbol)

        try:
            ids = self.subscription_ids[symbol]

            if "trades" in ids:
                self.info.unsubscribe({"type": "trades", "coin": coin}, ids["trades"])
            if "l2Book" in ids:
                self.info.unsubscribe({"type": "l2Book", "coin": coin}, ids["l2Book"])
            if "activeAssetCtx" in ids:
                self.info.unsubscribe({"type": "activeAssetCtx", "coin": coin}, ids["activeAssetCtx"])

            del self.subscription_ids[symbol]
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
            if symbol in self.trade_buffers:
                del self.trade_buffers[symbol]

            logger.info(f"Unsubscribed from {symbol}")

        except Exception as e:
            logger.error(f"Failed to unsubscribe {symbol}: {e}")

    def _on_trades(self, symbol: str, msg: dict):
        """Handle incoming trade messages"""
        try:
            if msg.get("channel") != "trades":
                return

            trades = msg.get("data", [])
            if not trades:
                return

            # Update freshness timestamp
            self.last_update_time["trades"] = time.time()

            with self.buffer_lock:
                buffer = self.trade_buffers.get(symbol)
                if not buffer:
                    return

                for trade in trades:
                    # SDK returns: coin, side (A=ask/sell, B=bid/buy), px, sz, hash, time
                    price = Decimal(str(trade["px"]))
                    size = Decimal(str(trade["sz"]))
                    side = trade["side"]  # "A" = taker sell, "B" = taker buy
                    notional = price * size
                    notional_float = float(notional)
                    # Classify before updating the tracker so the current trade
                    # does not immediately move its own threshold.
                    is_large = self.large_order_tracker.is_large_order(symbol, notional_float)
                    self.large_order_tracker.update(symbol, notional_float)

                    # Update buffer
                    if side == "B":  # Taker buy
                        buffer.taker_buy_volume += size
                        buffer.taker_buy_count += 1
                        buffer.taker_buy_notional += notional
                        if is_large:
                            buffer.large_buy_notional += notional
                            buffer.large_buy_count += 1
                    else:  # Taker sell (side == "A")
                        buffer.taker_sell_volume += size
                        buffer.taker_sell_count += 1
                        buffer.taker_sell_notional += notional
                        if is_large:
                            buffer.large_sell_notional += notional
                            buffer.large_sell_count += 1

                    buffer.total_volume += size
                    buffer.total_notional += notional

                    # Track high/low
                    if buffer.high_price is None or price > buffer.high_price:
                        buffer.high_price = price
                    if buffer.low_price is None or price < buffer.low_price:
                        buffer.low_price = price

        except Exception as e:
            logger.error(f"Error processing trades for {symbol}: {e}")

    def _on_l2book(self, symbol: str, msg: dict):
        """Handle incoming L2 orderbook messages"""
        try:
            if msg.get("channel") != "l2Book":
                return

            data = msg.get("data", {})
            if data:
                self.latest_orderbook[symbol] = data
                # Update freshness timestamp
                self.last_update_time["l2book"] = time.time()

        except Exception as e:
            logger.error(f"Error processing l2book for {symbol}: {e}")

    def _on_asset_ctx(self, symbol: str, msg: dict):
        """Handle incoming asset context messages"""
        try:
            channel = msg.get("channel")
            if channel not in ("activeAssetCtx", "activeSpotAssetCtx"):
                return

            data = msg.get("data", {})
            if data:
                self.latest_asset_ctx[symbol] = data
                # Update freshness timestamp
                self.last_update_time["asset_ctx"] = time.time()

        except Exception as e:
            logger.error(f"Error processing asset ctx for {symbol}: {e}")
