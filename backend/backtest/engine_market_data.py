"""
MarketData construction for the Program Backtest Engine.

Translates virtual account state, trigger context and recent trade history into
a program_trader MarketData object for strategy execution. Mixed into
ProgramBacktestEngine.
"""

import logging
from typing import Any, List

from .models import TriggerEvent, BacktestTradeRecord
from .virtual_account import VirtualAccount
from .historical_data_provider import HistoricalDataProvider

logger = logging.getLogger(__name__)


class MarketDataBuilderMixin:
    """Builds MarketData objects for backtest strategy execution."""

    def _build_market_data(
        self,
        account: VirtualAccount,
        data_provider: HistoricalDataProvider,
        trigger: TriggerEvent,
        trigger_symbol: str,
        recent_trades: List[BacktestTradeRecord] = None,
    ) -> Any:
        """Build MarketData object for strategy execution."""
        from program_trader.models import MarketData, Position, Trade
        from datetime import datetime, timezone

        # Convert virtual positions to Position objects
        positions = {}
        current_time_ms = trigger.timestamp  # Use trigger timestamp as current time in backtest
        for symbol, vpos in account.positions.items():
            # Calculate position timing information
            opened_at = vpos.entry_timestamp if vpos.entry_timestamp else None
            opened_at_str = None
            holding_duration_seconds = None
            holding_duration_str = None

            if opened_at and opened_at > 0:
                # Format opened_at as UTC string
                utc_dt = datetime.fromtimestamp(opened_at / 1000, tz=timezone.utc)
                opened_at_str = utc_dt.strftime('%Y-%m-%d %H:%M:%S UTC')

                # Calculate holding duration
                holding_duration_seconds = (current_time_ms - opened_at) / 1000
                hours = int(holding_duration_seconds // 3600)
                minutes = int((holding_duration_seconds % 3600) // 60)
                if hours > 0:
                    holding_duration_str = f"{hours}h {minutes}m"
                else:
                    holding_duration_str = f"{minutes}m"

            positions[symbol] = Position(
                symbol=symbol,
                side=vpos.side,
                size=vpos.size,
                entry_price=vpos.entry_price,
                unrealized_pnl=vpos.unrealized_pnl,
                leverage=vpos.leverage,
                liquidation_price=0,
                opened_at=opened_at,
                opened_at_str=opened_at_str,
                holding_duration_seconds=holding_duration_seconds,
                holding_duration_str=holding_duration_str,
            )

        # Convert recent trades to Trade objects (last 20 closed trades)
        trade_objects = []
        if recent_trades:
            closed_trades = [t for t in recent_trades if t.exit_price is not None][-20:]
            for t in closed_trades:
                trade_objects.append(Trade(
                    symbol=t.symbol,
                    side=t.side.capitalize(),  # "long" -> "Long"
                    size=t.size,
                    price=t.entry_price,
                    timestamp=t.timestamp,
                    pnl=t.pnl,
                ))

        # Build triggered signals info - pass through ALL fields from backtest service
        # Strategy code needs: metric, current_value, direction, ratio, threshold, etc.
        triggered_signals = []
        if trigger.triggered_signals:
            for sig in trigger.triggered_signals:
                # Pass through all signal data as-is
                signal_data = dict(sig)  # Copy all fields
                # Ensure current_value is set (backtest service uses 'value')
                if "current_value" not in signal_data and "value" in signal_data:
                    signal_data["current_value"] = signal_data["value"]
                triggered_signals.append(signal_data)

        # Build trigger_market_regime from trigger.market_regime
        trigger_market_regime = None
        if trigger.market_regime:
            from program_trader.models import RegimeInfo
            mr = trigger.market_regime
            trigger_market_regime = RegimeInfo(
                regime=mr.get("regime", "noise"),
                conf=mr.get("conf", 0.0),
                direction=mr.get("direction", "neutral"),
                reason=mr.get("reason", ""),
                indicators=mr.get("indicators", {}),
            )

        return MarketData(
            available_balance=account.balance,
            total_equity=account.equity,
            used_margin=account.get_used_margin(),
            margin_usage_percent=account.get_margin_usage_percent(),
            maintenance_margin=account.get_maintenance_margin(),
            trigger_symbol=trigger_symbol,
            trigger_type=trigger.trigger_type,
            positions=positions,
            recent_trades=trade_objects,
            # Trigger context (detailed)
            signal_pool_name=trigger.pool_name or "",
            pool_logic=trigger.pool_logic or "OR",
            triggered_signals=triggered_signals,
            trigger_market_regime=trigger_market_regime,
            _data_provider=data_provider,
        )
