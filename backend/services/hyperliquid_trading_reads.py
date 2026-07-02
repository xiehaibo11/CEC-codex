"""Hyperliquid trading client account and position read helpers."""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from services.exchanges.symbol_mapper import SymbolMapper
from services.hyperliquid_cache import update_account_state_cache, update_positions_cache
from services.hyperliquid_trading_history_reads import HyperliquidTradeHistoryReadsMixin
from services.hyperliquid_trading_order_reads import HyperliquidOrderReadsMixin

logger = logging.getLogger(__name__)

UNIFIED_ACCOUNT_MODES = ("unifiedAccount", "portfolioMargin")


class HyperliquidReadsMixin(HyperliquidTradeHistoryReadsMixin, HyperliquidOrderReadsMixin):
    """Read-only Hyperliquid queries composed into HyperliquidTradingClient."""

    def get_account_state(self, db: Session) -> Dict[str, Any]:
        self._validate_environment(db)

        try:
            logger.info(f"Fetching account state for account {self.account_id} on {self.environment}")
            user_state = self._fetch_user_state_with_hip3()
            margin_summary = user_state.get("crossMarginSummary") or user_state.get("marginSummary", {})

            total_equity = float(margin_summary.get("accountValue", 0) or 0)
            used_margin = float(margin_summary.get("totalMarginUsed", 0) or 0)
            available_balance = float(user_state.get("withdrawable", 0) or 0)

            account_mode = self._detect_account_mode()
            if account_mode in UNIFIED_ACCOUNT_MODES:
                try:
                    spot_balance = self._get_spot_balance()
                    total_equity = spot_balance["total_equity"]
                    available_balance = spot_balance["available_balance"]
                    used_margin = spot_balance["used_margin"]
                    print(
                        f"[UNIFIED ACCOUNT] account {self.account_id}: "
                        f"equity=${total_equity:.2f}, available=${available_balance:.2f}, "
                        f"hold=${used_margin:.2f}",
                        flush=True,
                    )
                except Exception as spot_err:
                    print(
                        f"[UNIFIED ACCOUNT] Failed to get spot balance for account "
                        f"{self.account_id}, falling back to perp state: {spot_err}",
                        flush=True,
                    )

            margin_usage_percent = round((used_margin / total_equity * 100), 2) if total_equity > 0 else 0
            result = {
                "environment": self.environment,
                "account_id": self.account_id,
                "total_equity": round(total_equity, 2),
                "available_balance": round(available_balance, 2),
                "used_margin": round(used_margin, 2),
                "maintenance_margin": round(used_margin * 0.5, 2),
                "margin_usage_percent": margin_usage_percent,
                "withdrawal_available": round(available_balance, 2),
                "wallet_address": self.wallet_address,
                "account_mode": account_mode,
                "timestamp": int(time.time() * 1000),
            }

            logger.debug(
                f"Account state: equity=${result['total_equity']:.2f}, "
                f"available=${result['available_balance']:.2f}"
            )
            update_account_state_cache(self.account_id, result, self.environment)
            self._record_exchange_action(
                action_type="fetch_account_state",
                status="success",
                symbol=None,
                request_payload={"account_id": self.account_id, "environment": self.environment},
                response_payload=None,
            )
            return result
        except Exception as err:
            self._record_exchange_action(
                action_type="fetch_account_state",
                status="error",
                symbol=None,
                request_payload={"account_id": self.account_id, "environment": self.environment},
                response_payload=None,
                error_message=str(err),
            )
            logger.error(f"Failed to get account state: {err}", exc_info=True)
            raise

    def get_positions(self, db: Session, include_timing: bool = False) -> List[Dict[str, Any]]:
        self._validate_environment(db)

        try:
            logger.info(f"Fetching positions for account {self.account_id} on {self.environment}")
            user_state = self._fetch_user_state_with_hip3()
            asset_positions = user_state.get("assetPositions", [])
            user_fills = self._load_position_timing_fills(db, include_timing)

            positions = []
            for asset_pos in asset_positions:
                position = self._format_position(asset_pos, user_fills)
                if position:
                    positions.append(position)

            logger.debug(f"Found {len(positions)} open positions")
            update_positions_cache(self.account_id, positions, self.environment)
            self._record_exchange_action(
                action_type="fetch_positions",
                status="success",
                symbol=None,
                request_payload={"account_id": self.account_id, "environment": self.environment},
                response_payload=None,
            )
            return positions
        except Exception as err:
            self._record_exchange_action(
                action_type="fetch_positions",
                status="error",
                symbol=None,
                request_payload={"account_id": self.account_id, "environment": self.environment},
                response_payload=None,
                error_message=str(err),
            )
            logger.error(f"Failed to get positions: {err}", exc_info=True)
            raise

    def _load_position_timing_fills(self, db: Session, include_timing: bool) -> List[Dict[str, Any]]:
        if not include_timing:
            return []
        try:
            user_fills = self._get_user_fills(db)
            logger.info(f"Retrieved {len(user_fills)} user fills for position timing calculation")
            return user_fills
        except Exception as fills_error:
            logger.warning(f"Failed to get user fills for position timing: {fills_error}")
            return []

    def _format_position(
        self,
        asset_pos: Dict[str, Any],
        user_fills: List[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        pos_data = asset_pos.get("position", {})
        try:
            position_size = float(pos_data.get("szi"))
        except (TypeError, ValueError):
            position_size = 0.0

        if abs(position_size) < 1e-8:
            return None

        coin = SymbolMapper.to_internal(pos_data.get("coin") or "", "hyperliquid")
        opened_at, opened_at_str, holding_seconds, holding_str = self._format_position_timing(
            coin,
            position_size,
            user_fills,
        )
        entry_px = float(pos_data.get("entryPx", 0) or 0)
        position_value = float(pos_data.get("positionValue", 0) or 0)
        leverage = pos_data.get("leverage") or {}

        return {
            "coin": coin,
            "szi": position_size,
            "entry_px": entry_px,
            "position_value": position_value,
            "unrealized_pnl": float(pos_data.get("unrealizedPnl", 0) or 0),
            "margin_used": float(pos_data.get("marginUsed", 0) or 0),
            "liquidation_px": float(pos_data.get("liquidationPx") or 0),
            "leverage": float(leverage.get("value", 0)),
            "side": "Long" if position_size > 0 else "Short",
            "opened_at": opened_at,
            "opened_at_str": opened_at_str,
            "holding_duration_seconds": holding_seconds,
            "holding_duration_str": holding_str,
            "return_on_equity": float(pos_data.get("returnOnEquity", 0) or 0),
            "max_leverage": float(pos_data.get("maxLeverage", 0) or 0),
            "cum_funding_all_time": float((pos_data.get("cumFunding") or {}).get("allTime", 0)),
            "cum_funding_since_open": float((pos_data.get("cumFunding") or {}).get("sinceOpen", 0)),
            "leverage_type": leverage.get("type"),
            "notional": position_value,
            "percentage": float(pos_data.get("returnOnEquity", 0) or 0) * 100,
            "contract_size": 1.0,
            "margin_mode": leverage.get("type", "cross"),
        }

    def _format_position_timing(
        self,
        coin: str,
        position_size: float,
        user_fills: List[Dict[str, Any]],
    ) -> tuple[Any, Any, Any, Any]:
        if not user_fills or not coin:
            return None, None, None, None

        opened_at = self._calculate_position_opened_time(coin, position_size, user_fills)
        if not opened_at:
            return None, None, None, None

        utc_dt = datetime.fromtimestamp(opened_at / 1000, tz=timezone.utc)
        opened_at_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        holding_seconds = (int(time.time() * 1000) - opened_at) / 1000
        hours = int(holding_seconds // 3600)
        minutes = int((holding_seconds % 3600) // 60)
        holding_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        return opened_at, opened_at_str, holding_seconds, holding_str
