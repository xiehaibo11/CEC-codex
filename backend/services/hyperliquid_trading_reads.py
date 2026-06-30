"""Hyperliquid trading client - account, position and order read helpers.

Extracted verbatim from ``hyperliquid_trading_client.py`` as a mixin to keep the
main client module focused. Composed into ``HyperliquidTradingClient``; no logic
changes were made to any method body.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.hyperliquid_cache import (
    update_account_state_cache,
    update_positions_cache,
)
from services.exchanges.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)

# Valid account modes returned by Hyperliquid userAbstraction API
UNIFIED_ACCOUNT_MODES = ("unifiedAccount", "portfolioMargin")


class HyperliquidReadsMixin:
    """Read-only Hyperliquid queries (account state, positions, fills, orders, stats).

    Relies on host-class attributes/methods (``self.sdk_info``, ``self.query_address``,
    ``self._validate_environment``, ``self._record_exchange_action``,
    ``self._detect_account_mode``, ``self._get_spot_balance``, ...); only valid when
    mixed into ``HyperliquidTradingClient``.
    """

    def get_account_state(self, db: Session) -> Dict[str, Any]:
        """
        Get current account state from Hyperliquid

        Returns account equity, available balance, margin usage, etc.

        Args:
            db: Database session

        Returns:
            Dict with:
                - environment: "testnet" or "mainnet"
                - account_id: Database account ID
                - total_equity: Total account value
                - available_balance: Available for new positions
                - used_margin: Margin currently used
                - maintenance_margin: Required maintenance margin
                - margin_usage_percent: Used margin / Total equity * 100
                - withdrawal_available: Amount available for withdrawal

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            logger.info(f"Fetching account state for account {self.account_id} on {self.environment}")

            # Use SDK Info.user_state for perp state (positions, maintenance margin)
            user_state = self._fetch_user_state_with_hip3()
            margin_summary = user_state.get('crossMarginSummary') or user_state.get('marginSummary', {})

            total_equity = float(margin_summary.get('accountValue', 0) or 0)
            used_margin = float(margin_summary.get('totalMarginUsed', 0) or 0)
            available_balance = float(user_state.get('withdrawable', 0) or 0)

            # Detect account mode via userAbstraction API
            account_mode = self._detect_account_mode()
            if account_mode in UNIFIED_ACCOUNT_MODES:
                # In Unified/Portfolio mode, clearinghouseState returns 0 for balance fields.
                # Real balance lives in spotClearinghouseState.
                try:
                    spot_balance = self._get_spot_balance()
                    total_equity = spot_balance["total_equity"]
                    available_balance = spot_balance["available_balance"]
                    used_margin = spot_balance["used_margin"]
                    print(
                        f"[UNIFIED ACCOUNT] account {self.account_id}: "
                        f"equity=${total_equity:.2f}, available=${available_balance:.2f}, "
                        f"hold=${used_margin:.2f}",
                        flush=True
                    )
                except Exception as spot_err:
                    # Fallback: if spot query fails, use perp state (may be 0)
                    print(
                        f"[UNIFIED ACCOUNT] Failed to get spot balance for account "
                        f"{self.account_id}, falling back to perp state: {spot_err}",
                        flush=True
                    )

            # Calculate margin usage percentage (round to 2 decimal places)
            margin_usage_percent = round((used_margin / total_equity * 100), 2) if total_equity > 0 else 0

            result = {
                'environment': self.environment,
                'account_id': self.account_id,
                'total_equity': round(total_equity, 2),
                'available_balance': round(available_balance, 2),
                'used_margin': round(used_margin, 2),
                'maintenance_margin': round(used_margin * 0.5, 2),  # Estimate: maintenance = 50% of initial
                'margin_usage_percent': margin_usage_percent,
                'withdrawal_available': round(available_balance, 2),
                'wallet_address': self.wallet_address,
                'account_mode': account_mode,
                'timestamp': int(time.time() * 1000)
            }

            logger.debug(f"Account state: equity=${result['total_equity']:.2f}, available=${result['available_balance']:.2f}")
            update_account_state_cache(self.account_id, result, self.environment)
            self._record_exchange_action(
                action_type="fetch_account_state",
                status="success",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "environment": self.environment,
                },
                response_payload=None,
            )

            return result

        except Exception as e:
            self._record_exchange_action(
                action_type="fetch_account_state",
                status="error",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "environment": self.environment,
                },
                response_payload=None,
                error_message=str(e),
            )
            logger.error(f"Failed to get account state: {e}", exc_info=True)
            raise

    def get_positions(self, db: Session, include_timing: bool = False) -> List[Dict[str, Any]]:
        """
        Get all open positions from Hyperliquid

        Args:
            db: Database session
            include_timing: If True, fetch user_fills to calculate position opened times.
                           Only needed for AI decision prompts. Default False to save API calls.

        Returns:
            List of position dicts, each with:
                - coin: Symbol name (e.g., "BTC")
                - szi: Position size (signed: positive=long, negative=short)
                - entry_px: Average entry price
                - position_value: Current position value
                - unrealized_pnl: Unrealized profit/loss
                - margin_used: Margin used for this position
                - liquidation_px: Liquidation price
                - leverage: Current leverage
                - opened_at: Timestamp when position was opened (only if include_timing=True)
                - opened_at_str: Human-readable opened time (only if include_timing=True)
                - holding_duration_seconds: How long position has been held (only if include_timing=True)
                - holding_duration_str: Human-readable holding duration (only if include_timing=True)

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            logger.info(f"Fetching positions for account {self.account_id} on {self.environment}")

            # Use SDK Info.user_state for positions (avoids CCXT spot market loading issues)
            user_state = self._fetch_user_state_with_hip3()
            asset_positions = user_state.get('assetPositions', [])

            # Get user fills to calculate position opened times (only when needed for AI prompts)
            user_fills = []
            if include_timing:
                try:
                    user_fills = self._get_user_fills(db)
                    logger.info(f"Retrieved {len(user_fills)} user fills for position timing calculation")
                except Exception as fills_error:
                    logger.warning(f"Failed to get user fills for position timing: {fills_error}")

            # Transform SDK positions to our format
            positions = []
            for asset_pos in asset_positions:
                pos_data = asset_pos.get('position', {})
                raw_size = pos_data.get('szi')
                try:
                    position_size = float(raw_size)
                except (TypeError, ValueError):
                    position_size = 0.0

                if abs(position_size) < 1e-8:
                    continue

                coin = SymbolMapper.to_internal(pos_data.get('coin') or "", "hyperliquid")
                side = 'Long' if position_size > 0 else 'Short'

                # Calculate position timing
                opened_at = None
                opened_at_str = None
                holding_duration_seconds = None
                holding_duration_str = None

                if user_fills and coin:
                    opened_at = self._calculate_position_opened_time(coin, position_size, user_fills)
                    if opened_at:
                        from datetime import datetime, timezone
                        import time as time_module

                        utc_dt = datetime.fromtimestamp(opened_at / 1000, tz=timezone.utc)
                        opened_at_str = utc_dt.strftime('%Y-%m-%d %H:%M:%S UTC')

                        current_time_ms = int(time_module.time() * 1000)
                        holding_duration_seconds = (current_time_ms - opened_at) / 1000

                        hours = int(holding_duration_seconds // 3600)
                        minutes = int((holding_duration_seconds % 3600) // 60)
                        if hours > 0:
                            holding_duration_str = f"{hours}h {minutes}m"
                        else:
                            holding_duration_str = f"{minutes}m"

                entry_px = float(pos_data.get('entryPx', 0) or 0)
                position_value = float(pos_data.get('positionValue', 0) or 0)

                positions.append({
                    'coin': coin,
                    'szi': position_size,
                    'entry_px': entry_px,
                    'position_value': position_value,
                    'unrealized_pnl': float(pos_data.get('unrealizedPnl', 0) or 0),
                    'margin_used': float(pos_data.get('marginUsed', 0) or 0),
                    'liquidation_px': float(pos_data.get('liquidationPx') or 0),
                    'leverage': float((pos_data.get('leverage') or {}).get('value', 0)),
                    'side': side,

                    'opened_at': opened_at,
                    'opened_at_str': opened_at_str,
                    'holding_duration_seconds': holding_duration_seconds,
                    'holding_duration_str': holding_duration_str,

                    'return_on_equity': float(pos_data.get('returnOnEquity', 0) or 0),
                    'max_leverage': float(pos_data.get('maxLeverage', 0) or 0),
                    'cum_funding_all_time': float((pos_data.get('cumFunding') or {}).get('allTime', 0)),
                    'cum_funding_since_open': float((pos_data.get('cumFunding') or {}).get('sinceOpen', 0)),
                    'leverage_type': (pos_data.get('leverage') or {}).get('type'),

                    'notional': position_value,
                    'percentage': float(pos_data.get('returnOnEquity', 0) or 0) * 100,
                    'contract_size': 1.0,
                    'margin_mode': (pos_data.get('leverage') or {}).get('type', 'cross')
                })

            logger.debug(f"Found {len(positions)} open positions")
            update_positions_cache(self.account_id, positions, self.environment)
            self._record_exchange_action(
                action_type="fetch_positions",
                status="success",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "environment": self.environment,
                },
                response_payload=None,
            )

            return positions

        except Exception as e:
            self._record_exchange_action(
                action_type="fetch_positions",
                status="error",
                symbol=None,
                request_payload={
                    "account_id": self.account_id,
                    "environment": self.environment,
                },
                response_payload=None,
                error_message=str(e),
            )
            logger.error(f"Failed to get positions: {e}", exc_info=True)
            raise

    def _get_user_fills(self, db: Session) -> List[Dict[str, Any]]:
        """
        Get all user fills (trade executions) from Hyperliquid SDK

        This method uses Hyperliquid SDK's Info.user_fills() to retrieve
        ALL historical trade executions for this wallet address.

        Args:
            db: Database session (for environment validation)

        Returns:
            List of fill dicts with fields:
                - coin: Symbol name
                - side: "A" (ask/sell) or "B" (bid/buy)
                - px: Execution price
                - sz: Size filled
                - time: Execution timestamp (milliseconds)
                - startPosition: Position before this fill
                - dir: Direction ("Open Long", "Close Long", etc.)
                - closedPnl: Realized PnL if position closed
                - oid: Order ID

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            logger.info(f"Fetching user fills for wallet {self.query_address} on {self.environment}")

            # Use SDK Info to get all user fills
            # Must use query_address (master wallet) instead of wallet_address (agent key)
            # because fills are associated with the master wallet on Hyperliquid
            fills = self.sdk_info.user_fills(self.query_address)
            for fill in fills:
                if isinstance(fill, dict) and fill.get('coin'):
                    fill['coin'] = SymbolMapper.to_internal(fill.get('coin'), "hyperliquid")

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

        except Exception as e:
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
                error_message=str(e),
            )
            logger.error(f"Failed to get user fills: {e}", exc_info=True)
            raise

    def query_order_by_oid(self, db: Session, order_id: int) -> Optional[Dict[str, Any]]:
        """
        Query order details by order ID from Hyperliquid API.

        Args:
            db: Database session (for environment validation)
            order_id: The order ID to query

        Returns:
            Order dict with status and statusTimestamp if found, None otherwise
        """
        self._validate_environment(db)

        try:
            logger.debug(f"Querying order {order_id} for wallet {self.query_address}")
            result = self.sdk_info.query_order_by_oid(self.query_address, order_id)
            return result
        except Exception as e:
            logger.warning(f"Failed to query order {order_id}: {e}")
            return None

    def get_order_trigger_time(self, db: Session, order_id: int) -> Optional[datetime]:
        """
        Get the actual trigger/fill time for an order.

        Args:
            db: Database session
            order_id: The order ID to query

        Returns:
            datetime of when the order was filled/triggered, or None if not available
        """
        result = self.query_order_by_oid(db, order_id)
        if not result:
            return None

        # Extract statusTimestamp from the response
        # Response format: {'status': 'order', 'order': {'order': {...}, 'status': 'filled', 'statusTimestamp': 1767580190625}}
        order_data = result.get("order", {})
        status_timestamp = order_data.get("statusTimestamp")

        if status_timestamp:
            try:
                # statusTimestamp is in milliseconds, return UTC without timezone info
                # to match database datetime format (all stored as UTC without tzinfo)
                return datetime.utcfromtimestamp(status_timestamp / 1000)
            except Exception as e:
                logger.warning(f"Failed to parse statusTimestamp {status_timestamp}: {e}")
                return None

        return None

    def _get_historical_orders(self, db: Session) -> List[Dict[str, Any]]:
        """
        Get historical orders from Hyperliquid SDK

        This method uses Hyperliquid SDK's Info.historical_orders() to retrieve
        up to 2000 most recent orders for this wallet address.

        Args:
            db: Database session (for environment validation)

        Returns:
            List of order dicts with status, fills, and execution details

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            logger.info(f"Fetching historical orders for wallet {self.query_address} on {self.environment}")

            # Use SDK Info to get historical orders (up to 2000 most recent)
            # Must use query_address (master wallet) for agent_key mode
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

        except Exception as e:
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
                error_message=str(e),
            )
            logger.error(f"Failed to get historical orders: {e}", exc_info=True)
            raise

    def _calculate_position_opened_time(self, symbol: str, current_position_size: float, fills: List[Dict[str, Any]]) -> Optional[int]:
        """
        Calculate when a position was opened based on user fills

        This method walks backwards through fills starting from the current position,
        subtracting each fill's effect until we reach the point where the position
        was first opened (when going back further would cross zero or change direction).

        Args:
            symbol: Asset symbol (e.g., "BTC")
            current_position_size: Current position size (signed: positive=long, negative=short)
            fills: List of all user fills (from _get_user_fills)

        Returns:
            Timestamp in milliseconds when position was first opened,
            or None if no fills found for this symbol
        """
        if not fills or abs(current_position_size) < 1e-8:
            return None

        # Filter fills for this symbol and sort by time (newest first)
        symbol_fills = [f for f in fills if f.get('coin') == symbol]
        symbol_fills.sort(key=lambda x: x.get('time', 0), reverse=True)

        if not symbol_fills:
            return None

        # Start from current position and walk backwards
        # Subtract each fill's effect to find when position started
        position_tracker = current_position_size
        earliest_time = None

        for fill in symbol_fills:
            sz = float(fill.get('sz', 0))
            side = fill.get('side', '')

            # Calculate what the position was BEFORE this fill
            # side "B" = buy (adds to position), "A" = sell (reduces position)
            if side == "B":
                position_before = position_tracker - sz
            elif side == "A":
                position_before = position_tracker + sz
            else:
                continue

            # Check if going back past this fill would cross zero or change direction
            # If so, this fill is where the current position started
            if abs(position_before) < 1e-8:
                # Position was zero before this fill - this is the opening fill
                earliest_time = fill.get('time')
                break
            elif (position_tracker > 0 and position_before < 0) or (position_tracker < 0 and position_before > 0):
                # Position changed direction - this fill opened the current position
                earliest_time = fill.get('time')
                break
            else:
                # This fill is part of the current position, keep going back
                earliest_time = fill.get('time')
                position_tracker = position_before

        return earliest_time

    def get_recent_closed_trades(self, db: Session, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent closed trades summary from historical orders

        This method analyzes historical orders to find recently closed positions
        and returns a summary with:
        - Symbol
        - Entry/exit time and prices
        - Holding duration
        - Realized PnL
        - Direction (long/short)

        Args:
            db: Database session (for environment validation)
            limit: Maximum number of closed trades to return (default 5)

        Returns:
            List of closed trade summaries, sorted by close time (most recent first)

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            # Get user fills which contain closedPnl information
            fills = self._get_user_fills(db)

            # Filter for fills that closed positions (have closedPnl)
            closed_fills = []
            for fill in fills:
                closed_pnl = fill.get('closedPnl')
                if closed_pnl and closed_pnl != '0.0':
                    closed_fills.append(fill)

            # Sort by time (newest first) and limit
            closed_fills.sort(key=lambda x: x.get('time', 0), reverse=True)
            closed_fills = closed_fills[:limit]

            # Build trade summaries
            trades = []
            for fill in closed_fills:
                from datetime import datetime, timezone

                close_time_ms = fill.get('time', 0)
                # Use UTC time (consistent with session context display)
                utc_dt = datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc)
                close_time = utc_dt.strftime('%Y-%m-%d %H:%M:%S UTC')

                trade = {
                    'symbol': fill.get('coin'),
                    'side': 'Long' if fill.get('side') == 'A' else 'Short',  # Closing long = selling (A)
                    'close_price': float(fill.get('px', 0)),
                    'size': float(fill.get('sz', 0)),
                    'close_time': close_time,
                    'close_timestamp': close_time_ms,
                    'realized_pnl': float(fill.get('closedPnl', 0)),
                    'direction': fill.get('dir', ''),
                }

                trades.append(trade)

            logger.info(f"Found {len(trades)} recent closed trades")
            return trades

        except Exception as e:
            logger.error(f"Failed to get recent closed trades: {e}", exc_info=True)
            return []

    def get_trading_stats(self, db: Session) -> Dict[str, Any]:
        """
        Get trading statistics including win rate, profit factor, etc.

        Uses official Hyperliquid portfolio API for accurate all-time PNL
        (includes fees and funding), combined with fills data for win/loss stats.

        Args:
            db: Database session (for environment validation)

        Returns:
            Dict with trading statistics

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            # Get official portfolio data for accurate PNL (includes fees/funding)
            portfolio_pnl = 0.0
            portfolio_volume = 0.0
            try:
                portfolio_data = self.sdk_info.portfolio(self.query_address)
                # Find allTime or perpAllTime data
                for item in portfolio_data:
                    if item[0] == 'allTime':
                        pnl_history = item[1].get('pnlHistory', [])
                        if pnl_history:
                            portfolio_pnl = float(pnl_history[-1][1])
                        portfolio_volume = float(item[1].get('vlm', 0))
                        break
            except Exception as e:
                logger.warning(f"Failed to get portfolio data: {e}")

            # Get fills for win/loss statistics
            fills = self._get_user_fills(db)
            closed_fills = []
            for fill in fills:
                closed_pnl = fill.get('closedPnl')
                if closed_pnl and closed_pnl != '0.0':
                    closed_fills.append({
                        'pnl': float(closed_pnl),
                        'time': fill.get('time', 0),
                        'symbol': fill.get('coin'),
                    })

            if not closed_fills:
                return {
                    'total_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0.0,
                    'total_pnl': round(portfolio_pnl, 2),
                    'volume': round(portfolio_volume, 2),
                    'avg_win': 0.0,
                    'avg_loss': 0.0,
                    'profit_factor': 0.0,
                    'gross_profit': 0.0,
                    'gross_loss': 0.0,
                }

            # Calculate win/loss statistics from fills
            wins = [t for t in closed_fills if t['pnl'] > 0]
            losses = [t for t in closed_fills if t['pnl'] < 0]

            total_trades = len(closed_fills)
            win_count = len(wins)
            loss_count = len(losses)

            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
            gross_profit = sum(t['pnl'] for t in wins) if wins else 0.0
            gross_loss = abs(sum(t['pnl'] for t in losses)) if losses else 0.0
            avg_win = gross_profit / win_count if win_count > 0 else 0.0
            avg_loss = -gross_loss / loss_count if loss_count > 0 else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

            stats = {
                'total_trades': total_trades,
                'wins': win_count,
                'losses': loss_count,
                'win_rate': round(win_rate, 1),
                'total_pnl': round(portfolio_pnl, 2),  # Official PNL (includes fees)
                'volume': round(portfolio_volume, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'profit_factor': round(profit_factor, 2),
                'gross_profit': round(gross_profit, 2),
                'gross_loss': round(gross_loss, 2),
            }

            logger.info(f"Trading stats: {win_count}W/{loss_count}L, PNL=${portfolio_pnl:.2f}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get trading stats: {e}", exc_info=True)
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'volume': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'gross_profit': 0.0,
                'gross_loss': 0.0,
                'error': str(e),
            }

    def get_open_orders(self, db: Session, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get current open orders (unfilled/partially filled orders)

        This method uses Hyperliquid SDK's Info.frontend_open_orders() to retrieve
        all open orders with complete frontend information including trigger conditions,
        TP/SL flags, and order types.

        Args:
            db: Database session (for environment validation)
            symbol: Optional symbol filter (e.g., "BTC"). If None, returns all symbols.

        Returns:
            List of open order dicts with fields:
                - order_id: Order ID
                - symbol: Symbol name
                - side: "Buy" or "Sell"
                - direction: "Close Short", "Close Long", "Open Long", "Open Short"
                - order_type: Order type (e.g., "Stop Limit", "Take Profit Limit", "Limit")
                - size: Current remaining size
                - original_size: Original order size
                - price: Limit price
                - order_value: Calculated order value (size * price)
                - reduce_only: Whether this is a reduce-only order
                - is_trigger: Whether this is a trigger order
                - trigger_condition: Trigger condition string (e.g., "Price above 87500")
                - trigger_price: Trigger price
                - is_position_tpsl: Whether this is a position-level TP/SL
                - tif: Time in force (may be null for trigger orders)
                - order_time: Order placement time (UTC string)
                - timestamp: Order placement timestamp (milliseconds)

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            logger.info(f"Fetching open orders for wallet {self.query_address} on {self.environment}")

            # Use SDK Info to get frontend open orders (includes trigger conditions, TP/SL info)
            # Must use query_address (master wallet) for agent_key mode
            raw_orders = self._fetch_frontend_open_orders_with_hip3()

            # Transform to simplified format for AI prompt
            orders = []
            for order in raw_orders:
                from datetime import datetime, timezone

                # Parse order timestamp
                timestamp_ms = order.get('timestamp', 0)
                utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                order_time = utc_dt.strftime('%Y-%m-%d %H:%M:%S UTC')

                # Determine direction based on side and reduce_only
                side_raw = order.get('side', '')
                reduce_only = order.get('reduceOnly', False)

                if side_raw == 'B':  # Buy
                    side = 'Buy'
                    direction = 'Close Short' if reduce_only else 'Open Long'
                else:  # 'A' = Ask/Sell
                    side = 'Sell'
                    direction = 'Close Long' if reduce_only else 'Open Short'

                # Calculate order value
                size = float(order.get('sz', 0))
                price = float(order.get('limitPx', 0))
                order_value = size * price

                # Extract trigger information
                trigger_condition = order.get('triggerCondition', '')
                trigger_price = order.get('triggerPx')

                order_symbol = SymbolMapper.to_internal(order.get('coin', ''), "hyperliquid")
                order_summary = {
                    'order_id': order.get('oid'),
                    'symbol': order_symbol,
                    'side': side,
                    'direction': direction,
                    'order_type': order.get('orderType', 'Limit'),
                    'size': size,
                    'original_size': float(order.get('origSz', 0)),
                    'price': price,
                    'order_value': order_value,
                    'reduce_only': reduce_only,
                    'is_trigger': order.get('isTrigger', False),
                    'trigger_condition': trigger_condition if trigger_condition else None,
                    'trigger_price': float(trigger_price) if trigger_price else None,
                    'is_position_tpsl': order.get('isPositionTpsl', False),
                    'tif': order.get('tif'),
                    'order_time': order_time,
                    'timestamp': timestamp_ms,
                }

                orders.append(order_summary)

            # Sort by timestamp (newest first)
            orders.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

            # Filter by symbol if specified
            if symbol:
                internal_symbol = SymbolMapper.to_internal(symbol, "hyperliquid")
                orders = [o for o in orders if o.get('symbol') == internal_symbol]
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

        except Exception as e:
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
                error_message=str(e),
            )
            logger.error(f"Failed to get open orders: {e}", exc_info=True)
            return []

    def _get_open_orders_raw(self, db: Session, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders (including TP/SL trigger orders) from Hyperliquid - returns raw SDK data

        INTERNAL USE ONLY: This method returns raw SDK data format for TP/SL management.
        For formatted order data, use get_open_orders() instead.

        Args:
            db: Database session
            symbol: Optional symbol filter (e.g., "BTC"). If None, returns all symbols.

        Returns:
            List of open order dicts with raw SDK fields:
                - oid: Order ID
                - coin: Symbol name
                - side: "B" (buy) or "A" (sell/ask)
                - sz: Order size
                - limitPx: Limit price
                - orderType: Order type info
                - triggerPx: Trigger price (for TP/SL orders)
                - tpsl: "tp" or "sl" (for TP/SL orders)
                - reduceOnly: Whether order is reduce-only

        Raises:
            EnvironmentMismatchError: If environment validation fails
        """
        self._validate_environment(db)

        try:
            logger.info(f"Fetching raw open orders for wallet {self.query_address} on {self.environment}")

            # Use SDK Info to get open orders (frontend_open_orders includes trigger orders)
            # Must use query_address (master wallet) for agent_key mode
            open_orders = self._fetch_frontend_open_orders_with_hip3()

            logger.debug(f"Retrieved {len(open_orders)} open orders for wallet {self.query_address}")

            # Filter by symbol if specified
            if symbol:
                internal_symbol = SymbolMapper.to_internal(symbol, "hyperliquid")
                open_orders = [
                    o for o in open_orders
                    if SymbolMapper.to_internal(o.get('coin', ''), "hyperliquid") == internal_symbol
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

        except Exception as e:
            self._record_exchange_action(
                action_type="fetch_open_orders_raw",
                status="error",
                symbol=symbol,
                request_payload={
                    "account_id": self.account_id,
                    "wallet_address": self.wallet_address,
                    "symbol_filter": symbol,
                },
                error_message=str(e),
            )
            logger.error(f"Failed to get raw open orders: {e}", exc_info=True)
            raise

    def get_tpsl_orders(self, db: Session, symbol: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get current TP and SL orders for a specific symbol

        Args:
            db: Database session
            symbol: Asset symbol (e.g., "BTC")

        Returns:
            Dict with:
                - tp: TP order dict or None (most recent if multiple exist)
                - sl: SL order dict or None (most recent if multiple exist)
                - all_tp_orders: List of ALL TP orders found
                - all_sl_orders: List of ALL SL orders found
        """
        open_orders = self._get_open_orders_raw(db, symbol)
        
        # Debug: log all open orders to understand structure
        import sys
        print(f"[TPSL DEBUG] {symbol} - Found {len(open_orders)} open orders", file=sys.stderr, flush=True)
        logger.info(f"[TPSL DEBUG] {symbol} - Found {len(open_orders)} open orders")
        for i, order in enumerate(open_orders):
            print(f"[TPSL DEBUG] Order {i}: {order}", file=sys.stderr, flush=True)
            logger.info(f"[TPSL DEBUG] Order {i}: {order}")
        
        # Collect ALL TP and SL orders (not just the first one)
        all_tp_orders = []
        all_sl_orders = []
        
        for order in open_orders:
            order_type = order.get('orderType', {})
            is_trigger = order.get('isTrigger', False)
            trigger_px = order.get('triggerPx')
            trigger_condition = order.get('triggerCondition', '')
            
            # Debug: log order type structure
            logger.debug(f"[TPSL DEBUG] Order type: {order_type}, type={type(order_type)}, isTrigger={is_trigger}")
            
            # Determine if this is a TP or SL order
            # Support BOTH formats:
            # 1. Dict format: orderType = {"trigger": {"tpsl": "tp", "triggerPx": ...}}
            # 2. String format: orderType = "Take Profit Limit" or "Stop Limit"
            
            tpsl_type = None
            trigger_price = None
            
            # Format 1: Dict with trigger info
            if isinstance(order_type, dict) and 'trigger' in order_type:
                trigger_info = order_type.get('trigger', {})
                tpsl_type = trigger_info.get('tpsl')
                trigger_price = float(trigger_info.get('triggerPx', 0))
                logger.info(f"[TPSL DEBUG] Found dict trigger order: tpsl={tpsl_type}, trigger_price={trigger_price}")
            
            # Format 2: String orderType (from frontend_open_orders)
            elif isinstance(order_type, str) and is_trigger:
                # Parse orderType string: "Take Profit Limit" or "Stop Limit"
                order_type_lower = order_type.lower()
                if 'take profit' in order_type_lower:
                    tpsl_type = 'tp'
                elif 'stop' in order_type_lower and 'limit' in order_type_lower:
                    tpsl_type = 'sl'
                
                # Get trigger price from triggerPx field
                if trigger_px:
                    try:
                        trigger_price = float(trigger_px)
                    except (ValueError, TypeError):
                        trigger_price = 0
                
                logger.info(f"[TPSL DEBUG] Found string trigger order: orderType='{order_type}', tpsl={tpsl_type}, trigger_price={trigger_price}")
            
            # Format 3: Check triggerCondition as fallback
            elif is_trigger and trigger_condition:
                # Parse triggerCondition: "Price above 130" (TP) or "Price below 125.5" (SL)
                if 'above' in trigger_condition.lower():
                    tpsl_type = 'tp'
                elif 'below' in trigger_condition.lower():
                    tpsl_type = 'sl'
                
                if trigger_px:
                    try:
                        trigger_price = float(trigger_px)
                    except (ValueError, TypeError):
                        trigger_price = 0
                
                logger.info(f"[TPSL DEBUG] Found trigger by condition: condition='{trigger_condition}', tpsl={tpsl_type}, trigger_price={trigger_price}")
            
            # If we identified a TP or SL order, add it to the list
            if tpsl_type and trigger_price:
                order_dict = {
                    'oid': order.get('oid'),
                    'trigger_price': trigger_price,
                    'limit_price': float(order.get('limitPx', 0)),
                    'size': float(order.get('sz', 0)),
                    'side': order.get('side'),
                    'reduce_only': order.get('reduceOnly', True),
                    'timestamp': order.get('timestamp', 0),
                }
                
                if tpsl_type == 'tp':
                    all_tp_orders.append(order_dict)
                    logger.info(f"[TPSL DEBUG] Identified TP order: {order_dict}")
                elif tpsl_type == 'sl':
                    all_sl_orders.append(order_dict)
                    logger.info(f"[TPSL DEBUG] Identified SL order: {order_dict}")
        
        # Return the most recent order of each type (for backward compatibility)
        # but also include all orders for cleanup
        tp_order = all_tp_orders[0] if all_tp_orders else None
        sl_order = all_sl_orders[0] if all_sl_orders else None
        
        logger.info(f"[TPSL] {symbol} - Found {len(all_tp_orders)} TP orders, {len(all_sl_orders)} SL orders")
        logger.info(f"[TPSL] {symbol} - Primary TP={tp_order}, Primary SL={sl_order}")
        
        return {
            'tp': tp_order, 
            'sl': sl_order,
            'all_tp_orders': all_tp_orders,
            'all_sl_orders': all_sl_orders,
        }
