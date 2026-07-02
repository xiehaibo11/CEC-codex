"""Hyperliquid trade history and statistics read helpers."""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.exchanges.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)


class HyperliquidTradeHistoryReadsMixin:
    """Trade fill, history, and statistics reads for Hyperliquid clients."""

    def _get_user_fills(self, db: Session) -> List[Dict[str, Any]]:
        self._validate_environment(db)

        try:
            logger.info(f"Fetching user fills for wallet {self.query_address} on {self.environment}")
            fills = self.sdk_info.user_fills(self.query_address)
            for fill in fills:
                if isinstance(fill, dict) and fill.get("coin"):
                    fill["coin"] = SymbolMapper.to_internal(fill.get("coin"), "hyperliquid")

            logger.debug(f"Retrieved {len(fills)} fills for wallet {self.query_address}")
            self._record_exchange_action(
                action_type="fetch_user_fills",
                status="success",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "environment": self.environment,
                },
                response_payload=None,
            )
            return fills
        except Exception as err:
            self._record_exchange_action(
                action_type="fetch_user_fills",
                status="error",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "environment": self.environment,
                },
                response_payload=None,
                error_message=str(err),
            )
            logger.error(f"Failed to get user fills: {err}", exc_info=True)
            raise

    def _get_historical_orders(self, db: Session) -> List[Dict[str, Any]]:
        self._validate_environment(db)

        try:
            logger.info(f"Fetching historical orders for wallet {self.query_address} on {self.environment}")
            orders = self.sdk_info.historical_orders(self.query_address)
            logger.debug(f"Retrieved {len(orders)} historical orders for wallet {self.query_address}")
            self._record_exchange_action(
                action_type="fetch_historical_orders",
                status="success",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "environment": self.environment,
                },
                response_payload=None,
            )
            return orders
        except Exception as err:
            self._record_exchange_action(
                action_type="fetch_historical_orders",
                status="error",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "environment": self.environment,
                },
                response_payload=None,
                error_message=str(err),
            )
            logger.error(f"Failed to get historical orders: {err}", exc_info=True)
            raise

    def _calculate_position_opened_time(
        self,
        symbol: str,
        current_position_size: float,
        fills: List[Dict[str, Any]],
    ) -> Optional[int]:
        if not fills or abs(current_position_size) < 1e-8:
            return None

        symbol_fills = [f for f in fills if f.get("coin") == symbol]
        symbol_fills.sort(key=lambda x: x.get("time", 0), reverse=True)
        if not symbol_fills:
            return None

        position_tracker = current_position_size
        earliest_time = None

        for fill in symbol_fills:
            size = float(fill.get("sz", 0))
            side = fill.get("side", "")
            if side == "B":
                position_before = position_tracker - size
            elif side == "A":
                position_before = position_tracker + size
            else:
                continue

            if abs(position_before) < 1e-8:
                earliest_time = fill.get("time")
                break
            if (position_tracker > 0 and position_before < 0) or (
                position_tracker < 0 and position_before > 0
            ):
                earliest_time = fill.get("time")
                break

            earliest_time = fill.get("time")
            position_tracker = position_before

        return earliest_time

    def get_recent_closed_trades(self, db: Session, limit: int = 5) -> List[Dict[str, Any]]:
        self._validate_environment(db)

        try:
            fills = self._get_user_fills(db)
            closed_fills = [
                fill
                for fill in fills
                if fill.get("closedPnl") and fill.get("closedPnl") != "0.0"
            ]
            closed_fills.sort(key=lambda x: x.get("time", 0), reverse=True)

            trades = []
            for fill in closed_fills[:limit]:
                close_time_ms = fill.get("time", 0)
                utc_dt = datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc)
                trades.append({
                    "symbol": fill.get("coin"),
                    "side": "Long" if fill.get("side") == "A" else "Short",
                    "close_price": float(fill.get("px", 0)),
                    "size": float(fill.get("sz", 0)),
                    "close_time": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "close_timestamp": close_time_ms,
                    "realized_pnl": float(fill.get("closedPnl", 0)),
                    "direction": fill.get("dir", ""),
                })

            logger.info(f"Found {len(trades)} recent closed trades")
            return trades
        except Exception as err:
            logger.error(f"Failed to get recent closed trades: {err}", exc_info=True)
            return []

    def get_trading_stats(self, db: Session) -> Dict[str, Any]:
        self._validate_environment(db)

        try:
            portfolio_pnl, portfolio_volume = self._get_portfolio_stats()
            closed_fills = self._get_closed_fill_pnls(db)
            if not closed_fills:
                return _empty_trading_stats(portfolio_pnl, portfolio_volume)

            wins = [trade for trade in closed_fills if trade["pnl"] > 0]
            losses = [trade for trade in closed_fills if trade["pnl"] < 0]

            win_count = len(wins)
            loss_count = len(losses)
            total_trades = len(closed_fills)
            gross_profit = sum(trade["pnl"] for trade in wins) if wins else 0.0
            gross_loss = abs(sum(trade["pnl"] for trade in losses)) if losses else 0.0

            stats = {
                "total_trades": total_trades,
                "wins": win_count,
                "losses": loss_count,
                "win_rate": round((win_count / total_trades * 100) if total_trades else 0.0, 1),
                "total_pnl": round(portfolio_pnl, 2),
                "volume": round(portfolio_volume, 2),
                "avg_win": round(gross_profit / win_count, 2) if win_count else 0.0,
                "avg_loss": round(-gross_loss / loss_count, 2) if loss_count else 0.0,
                "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else 0.0,
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
            }
            logger.info(f"Trading stats: {win_count}W/{loss_count}L, PNL=${portfolio_pnl:.2f}")
            return stats
        except Exception as err:
            logger.error(f"Failed to get trading stats: {err}", exc_info=True)
            stats = _empty_trading_stats(0.0, 0.0)
            stats["error"] = str(err)
            return stats

    def _get_portfolio_stats(self) -> tuple[float, float]:
        portfolio_pnl = 0.0
        portfolio_volume = 0.0
        try:
            portfolio_data = self.sdk_info.portfolio(self.query_address)
            for item in portfolio_data:
                if item[0] != "allTime":
                    continue
                pnl_history = item[1].get("pnlHistory", [])
                if pnl_history:
                    portfolio_pnl = float(pnl_history[-1][1])
                portfolio_volume = float(item[1].get("vlm", 0))
                break
        except Exception as err:
            logger.warning(f"Failed to get portfolio data: {err}")
        return portfolio_pnl, portfolio_volume

    def _get_closed_fill_pnls(self, db: Session) -> List[Dict[str, Any]]:
        closed_fills = []
        for fill in self._get_user_fills(db):
            closed_pnl = fill.get("closedPnl")
            if closed_pnl and closed_pnl != "0.0":
                closed_fills.append({
                    "pnl": float(closed_pnl),
                    "time": fill.get("time", 0),
                    "symbol": fill.get("coin"),
                })
        return closed_fills


def _empty_trading_stats(total_pnl: float, volume: float) -> Dict[str, Any]:
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
