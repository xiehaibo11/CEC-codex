"""
Trade history and statistics methods for BinanceTradingClient.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BinanceTradingHistoryMixin:
    """Closed trades, fills, income, stats, and rebate methods."""

    def get_recent_closed_trades(self, db=None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent closed trades in unified format (compatible with HyperliquidTradingClient).

        Uses Binance's /fapi/v1/userTrades endpoint to get trade history,
        then filters for trades that closed positions (have realizedPnl != 0).
        """
        # Get all trades from last 7 days (Binance default)
        params = {"limit": 1000}  # Get more to filter
        raw_trades = self._request("GET", "/fapi/v1/userTrades", params, signed=True)

        # Filter for trades with realized PnL (position closures)
        closed_trades = []
        for t in raw_trades:
            realized_pnl = float(t.get("realizedPnl", 0))
            if realized_pnl != 0:
                sym = self._to_internal_symbol(t.get("symbol", ""))
                side = t.get("side", "")
                trade_time_ms = t.get("time", 0)
                close_time = datetime.fromtimestamp(trade_time_ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if trade_time_ms else "N/A"

                # Direction: if SELL with positive PnL = closed long, etc.
                if realized_pnl > 0:
                    direction = "WIN"
                else:
                    direction = "LOSS"

                closed_trades.append({
                    "symbol": sym,
                    "side": side,
                    "close_time": close_time,
                    "close_timestamp": trade_time_ms,
                    "close_price": float(t.get("price", 0)),
                    "realized_pnl": realized_pnl,
                    "direction": direction,
                    "size": float(t.get("qty", 0)),
                })

        # Sort by time (newest first) and limit
        closed_trades.sort(key=lambda x: x.get("close_timestamp", 0), reverse=True)
        return closed_trades[:limit]

    def get_income_history(
        self,
        income_type: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get income history including realized PnL, funding fees, commissions.

        Args:
            income_type: Filter by type (REALIZED_PNL, FUNDING_FEE, COMMISSION, etc.)
            start_time: Start timestamp in ms
            end_time: End timestamp in ms
            limit: Max records (default 1000)

        Returns:
            List of income records
        """
        params = {"limit": limit}
        if income_type:
            params["incomeType"] = income_type
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return self._request("GET", "/fapi/v1/income", params, signed=True)

    def get_trading_stats(self, db=None) -> Dict[str, Any]:
        """
        Get trading statistics including win rate, profit factor, etc.

        Similar to Hyperliquid's get_trading_stats for consistency.
        """
        try:
            # Get income history for realized PnL totals
            income_data = self.get_income_history(income_type="REALIZED_PNL")

            # Get user trades for win/loss calculation
            params = {"limit": 1000}
            raw_trades = self._request("GET", "/fapi/v1/userTrades", params, signed=True)

            # Filter trades with realized PnL (position closures)
            closed_fills = []
            for t in raw_trades:
                realized_pnl = float(t.get("realizedPnl", 0))
                if realized_pnl != 0:
                    closed_fills.append({
                        "pnl": realized_pnl,
                        "time": t.get("time", 0),
                        "symbol": self._to_internal_symbol(t.get("symbol", "")),
                    })

            # Calculate total PnL from income history
            total_pnl = sum(float(i.get("income", 0)) for i in income_data)

            # Calculate volume from trades
            volume = sum(
                float(t.get("qty", 0)) * float(t.get("price", 0))
                for t in raw_trades
            )

            if not closed_fills:
                return {
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "total_pnl": round(total_pnl, 2),
                    "volume": round(volume, 2),
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                    "profit_factor": 0.0,
                    "gross_profit": 0.0,
                    "gross_loss": 0.0,
                }

            # Calculate win/loss statistics
            wins = [t for t in closed_fills if t["pnl"] > 0]
            losses = [t for t in closed_fills if t["pnl"] < 0]

            total_trades = len(closed_fills)
            win_count = len(wins)
            loss_count = len(losses)

            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
            gross_profit = sum(t["pnl"] for t in wins) if wins else 0.0
            gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 0.0
            avg_win = gross_profit / win_count if win_count > 0 else 0.0
            avg_loss = -gross_loss / loss_count if loss_count > 0 else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

            stats = {
                "total_trades": total_trades,
                "wins": win_count,
                "losses": loss_count,
                "win_rate": round(win_rate, 1),
                "total_pnl": round(total_pnl, 2),
                "volume": round(volume, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "profit_factor": round(profit_factor, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
            }

            logger.info(f"[BINANCE] Trading stats: {win_count}W/{loss_count}L, PNL=${total_pnl:.2f}")
            return stats

        except Exception as e:
            logger.error(f"[BINANCE] Failed to get trading stats: {e}", exc_info=True)
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "volume": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "error": str(e),
            }

    def get_user_fills(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get all user fills (trade executions) from Binance.

        Similar to Hyperliquid's _get_user_fills() for PnL sync.
        """
        params = {"limit": limit}
        raw_trades = self._request("GET", "/fapi/v1/userTrades", params, signed=True)

        # Get order info to map orderId -> clientOrderId for TP/SL detection
        # TP/SL orders triggered from Algo orders have clientOrderId like "TP_123" or "SL_123"
        order_info = {}
        try:
            all_orders = self._request("GET", "/fapi/v1/allOrders", {"limit": limit}, signed=True)
            for o in all_orders:
                order_info[str(o.get("orderId", ""))] = o.get("clientOrderId", "")
        except Exception as e:
            logger.warning(f"[BINANCE] Failed to get order info for TP/SL detection: {e}")

        fills = []
        for t in raw_trades:
            order_id = str(t.get("orderId", ""))
            client_order_id = order_info.get(order_id, "")

            # Detect TP/SL orders by clientOrderId pattern (e.g., "TP_12345" or "SL_12345")
            main_order_id = None
            order_type = "main"
            if client_order_id.startswith("TP_"):
                main_order_id = client_order_id[3:]  # Extract main order ID after "TP_"
                order_type = "tp"
            elif client_order_id.startswith("SL_"):
                main_order_id = client_order_id[3:]  # Extract main order ID after "SL_"
                order_type = "sl"

            # Convert Binance format to unified format (compatible with Hyperliquid)
            fills.append({
                "oid": order_id,
                "coin": self._to_internal_symbol(t.get("symbol", "")),
                "side": "B" if t.get("side") == "BUY" else "A",
                "px": str(t.get("price", "0")),
                "sz": str(t.get("qty", "0")),
                "time": t.get("time", 0),
                "closedPnl": str(t.get("realizedPnl", "0")),
                "fee": str(t.get("commission", "0")),
                "main_order_id": main_order_id,
                "order_type": order_type,
            })

        logger.info(f"[BINANCE] Retrieved {len(fills)} user fills")
        return fills

    def check_rebate_eligibility(self) -> Dict[str, Any]:
        """
        Check if the user is eligible for API broker rebate.

        Uses Binance API endpoint: GET /fapi/v1/apiReferral/ifNewUser
        """
        try:
            # brokerId is required for this endpoint
            params = {"brokerId": self.broker_id} if self.broker_id else {}
            result = self._request("GET", "/fapi/v1/apiReferral/ifNewUser", params, signed=True)

            rebate_working = result.get("rebateWorking", False)
            is_new_user = result.get("ifNewUser", False)

            logger.info(
                f"[BINANCE] Rebate eligibility check: "
                f"rebateWorking={rebate_working}, ifNewUser={is_new_user}"
            )

            return {
                "eligible": rebate_working and is_new_user,
                "rebate_working": rebate_working,
                "is_new_user": is_new_user,
                "raw_response": result,
            }
        except Exception as e:
            logger.error(f"[BINANCE] Failed to check rebate eligibility: {e}")
            # Return ineligible on error to be safe
            return {
                "eligible": False,
                "rebate_working": False,
                "is_new_user": False,
                "error": str(e),
            }
