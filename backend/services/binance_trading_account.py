"""
Account and position read methods for BinanceTradingClient.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BinanceTradingAccountMixin:
    """Account, balance, and position methods."""

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get current price ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTC')

        Returns:
            Dict with price info:
            - symbol: Trading pair
            - price: Current price
        """
        binance_symbol = self._to_binance_symbol(symbol)
        result = self._request("GET", "/fapi/v1/ticker/price", {"symbol": binance_symbol})
        return {
            "symbol": symbol,
            "price": float(result.get("price", 0)),
            "binance_symbol": binance_symbol,
        }

    def get_account(self) -> Dict[str, Any]:
        """
        Get full account information including balances and positions.

        Returns:
            Account info dict with assets and positions arrays
        """
        return self._request("GET", "/fapi/v3/account", signed=True)

    def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance summary.

        Returns:
            Dict with balance fields mapped to unified format:
            - total_equity: Total wallet balance + unrealized PnL
            - available_balance: Available for trading
            - used_margin: Total initial margin
            - maintenance_margin: Total maintenance margin
            - unrealized_pnl: Total unrealized profit
            - margin_usage_percent: Margin usage percentage
        """
        account = self.get_account()

        total_equity = float(account.get("totalMarginBalance", 0))
        used_margin = float(account.get("totalInitialMargin", 0))
        margin_usage_percent = (used_margin / total_equity * 100) if total_equity > 0 else 0.0

        return {
            "environment": self.environment,
            "total_equity": total_equity,
            "available_balance": float(account.get("availableBalance", 0)),
            "used_margin": used_margin,
            "maintenance_margin": float(account.get("totalMaintMargin", 0)),
            "unrealized_pnl": float(account.get("totalUnrealizedProfit", 0)),
            "total_wallet_balance": float(account.get("totalWalletBalance", 0)),
            "margin_usage_percent": round(margin_usage_percent, 1),
            "timestamp": self._get_timestamp(),
            "source": "live",
        }

    def get_positions(self, db=None, include_timing: bool = False) -> List[Dict[str, Any]]:
        """
        Get all open positions with unified field format (compatible with Hyperliquid).

        Uses /fapi/v3/positionRisk endpoint which provides complete position data
        including entryPrice, markPrice, and liquidationPrice.
        """
        # Use positionRisk endpoint for complete position data
        position_risk = self._request("GET", "/fapi/v3/positionRisk", signed=True)
        positions = []
        user_fills: List[Dict[str, Any]] = []

        if include_timing:
            try:
                user_fills = self.get_user_fills(limit=1000)
            except Exception as e:
                logger.warning(f"[BINANCE] Failed to get user fills for position timing: {e}")

        # Build max leverage map from leverageBracket API (one call for all symbols)
        max_leverage_map = {}
        open_positions = [p for p in position_risk if float(p.get("positionAmt", 0)) != 0]
        if open_positions:
            try:
                brackets = self._request("GET", "/fapi/v1/leverageBracket", signed=True)
                for item in brackets:
                    symbol = item.get("symbol", "")
                    bracket_list = item.get("brackets", [])
                    if bracket_list:
                        # First bracket has the highest allowed leverage
                        max_lev = bracket_list[0].get("initialLeverage", 0)
                        # Store with USDT suffix removed
                        clean_symbol = symbol[:-4] if symbol.endswith("USDT") else symbol
                        max_leverage_map[clean_symbol] = max_lev
            except Exception as e:
                logger.warning(f"[BINANCE] Failed to fetch leverage brackets: {e}")

        for pos in position_risk:
            position_amt = float(pos.get("positionAmt", 0))
            if position_amt == 0:
                continue  # Skip empty positions

            symbol = pos.get("symbol", "")
            # Remove USDT suffix for internal format
            if symbol.endswith("USDT"):
                symbol = symbol[:-4]

            entry_price = float(pos.get("entryPrice", 0))
            notional = abs(float(pos.get("notional", 0)))
            initial_margin = float(pos.get("initialMargin", 0))

            # Calculate leverage from notional / initialMargin
            leverage = 1
            if initial_margin > 0:
                leverage = round(notional / initial_margin)

            # Determine margin type from isolatedMargin field
            isolated_margin = float(pos.get("isolatedMargin", 0))
            leverage_type = "isolated" if isolated_margin > 0 else "cross"

            # Determine side from position amount (positive=Long, negative=Short)
            side = "Long" if position_amt > 0 else "Short"

            opened_at = None
            opened_at_str = None
            holding_duration_seconds = None
            holding_duration_str = None

            if include_timing and user_fills and symbol:
                opened_at = self._calculate_position_opened_time(symbol, position_amt, user_fills)
                if opened_at:
                    utc_dt = datetime.utcfromtimestamp(opened_at / 1000)
                    opened_at_str = utc_dt.strftime('%Y-%m-%d %H:%M:%S UTC')

                    current_time_ms = self._get_timestamp()
                    holding_duration_seconds = (current_time_ms - opened_at) / 1000
                    hours = int(holding_duration_seconds // 3600)
                    minutes = int((holding_duration_seconds % 3600) // 60)
                    if hours > 0:
                        holding_duration_str = f"{hours}h {minutes}m"
                    else:
                        holding_duration_str = f"{minutes}m"

            positions.append({
                # Unified fields (Hyperliquid-compatible)
                "coin": symbol,
                "szi": position_amt,
                "entry_px": entry_price,
                "position_value": notional,
                "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
                "leverage": leverage,
                "liquidation_px": float(pos.get("liquidationPrice", 0)),
                "margin_used": initial_margin,
                "leverage_type": leverage_type,
                "side": side,  # Added: position direction for compatibility
                # Additional Binance-specific fields (for reference)
                "symbol": symbol,  # Alias for coin
                "mark_price": float(pos.get("markPrice", 0)),
                "maint_margin": float(pos.get("maintMargin", 0)),
                "position_side": pos.get("positionSide", "BOTH"),
                "max_leverage": max_leverage_map.get(symbol, 0),
                "opened_at": opened_at,
                "opened_at_str": opened_at_str,
                "holding_duration_seconds": holding_duration_seconds,
                "holding_duration_str": holding_duration_str,
            })

        return positions

    def _calculate_position_opened_time(
        self,
        symbol: str,
        current_position_size: float,
        fills: List[Dict[str, Any]],
    ) -> Optional[int]:
        """
        Calculate when the current position was opened based on user fills.

        Mirrors Hyperliquid's timing logic so Program Trader gets the same
        timing semantics across exchanges.
        """
        if not fills or abs(current_position_size) < 1e-8:
            return None

        symbol_fills = [f for f in fills if f.get("coin") == symbol]
        symbol_fills.sort(key=lambda x: x.get("time", 0), reverse=True)

        if not symbol_fills:
            return None

        position_tracker = current_position_size
        earliest_time = None

        for fill in symbol_fills:
            sz = float(fill.get("sz", 0) or 0)
            side = fill.get("side", "")

            if side == "B":
                position_before = position_tracker - sz
            elif side == "A":
                position_before = position_tracker + sz
            else:
                continue

            if abs(position_before) < 1e-8:
                earliest_time = fill.get("time")
                break
            elif (position_tracker > 0 and position_before < 0) or (position_tracker < 0 and position_before > 0):
                earliest_time = fill.get("time")
                break
            else:
                earliest_time = fill.get("time")
                position_tracker = position_before

        return earliest_time

    def get_account_state(self, db=None) -> Dict[str, Any]:
        """
        Get account state in unified format (compatible with HyperliquidTradingClient).

        Returns:
            Dict with: available_balance, total_equity, used_margin,
                      margin_usage_percent, maintenance_margin
        """
        balance = self.get_balance()
        return {
            "available_balance": balance.get("available_balance", 0.0),
            "total_equity": balance.get("total_equity", 0.0),
            "used_margin": balance.get("used_margin", 0.0),
            "margin_usage_percent": balance.get("margin_usage_percent", 0.0),
            "maintenance_margin": balance.get("maintenance_margin", 0.0),
        }

    def get_rate_limit(self) -> Dict[str, Any]:
        """
        Get current API rate limit info from last request's response header.

        Returns:
            Dict with: used_weight, weight_cap, remaining, usage_percent
        """
        remaining = self._weight_cap - self._last_used_weight
        usage_percent = (self._last_used_weight / self._weight_cap * 100) if self._weight_cap > 0 else 0
        return {
            "used_weight": self._last_used_weight,
            "weight_cap": self._weight_cap,
            "remaining": remaining,
            "usage_percent": round(usage_percent, 1),
        }
