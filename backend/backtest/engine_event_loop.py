"""
Event-loop execution for the Program Backtest Engine.

Drives trigger processing (signal + dynamically generated scheduled triggers),
strategy execution, TP/SL settlement and equity tracking. Provides both the
batch event loop and the streaming generator variant. Mixed into
ProgramBacktestEngine; relies on self._build_market_data.
"""

import logging
from typing import Dict, List, Any

from .models import (
    BacktestConfig,
    TriggerEvent,
    BacktestTradeRecord,
    TriggerExecutionResult,
)
from .virtual_account import VirtualAccount
from .execution_simulator import ExecutionSimulator
from .historical_data_provider import HistoricalDataProvider

logger = logging.getLogger(__name__)


class EventLoopMixin:
    """Batch and streaming event-loop execution for ProgramBacktestEngine."""

    def _run_event_loop(
        self,
        config: BacktestConfig,
        signal_triggers: List[TriggerEvent],
        account: VirtualAccount,
        simulator: ExecutionSimulator,
        data_provider: HistoricalDataProvider,
    ) -> tuple:
        """
        Run the main event loop with dynamic scheduled trigger generation.

        Signal triggers have higher priority. Each trigger (signal or scheduled)
        resets the scheduled trigger timer, matching real-time execution behavior.
        """
        from program_trader.executor import SandboxExecutor
        from concurrent.futures import ThreadPoolExecutor

        backtest_thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backtest")
        executor = SandboxExecutor(timeout_seconds=5, thread_pool=backtest_thread_pool)
        trades: List[BacktestTradeRecord] = []
        equity_curve: List[Dict[str, Any]] = []
        all_triggers: List[TriggerEvent] = []  # Track all triggers for logging

        # Scheduled trigger state - now uses seconds directly
        scheduled_interval_ms = None
        if config.scheduled_interval_sec:
            scheduled_interval_ms = config.scheduled_interval_sec * 1000

        # Initialize: next scheduled trigger is start_time + interval
        last_trigger_time = config.start_time_ms

        def execute_trigger(trigger: TriggerEvent) -> int:
            """Execute a single trigger and return the trigger timestamp."""
            nonlocal last_trigger_time

            all_triggers.append(trigger)

            # Set current time
            data_provider.set_current_time(trigger.timestamp)

            # Get current prices
            prices = data_provider.get_current_prices(config.symbols)
            if not prices:
                return trigger.timestamp

            # Check TP/SL triggers first
            tp_sl_trades = simulator.check_tp_sl_triggers(account, prices, trigger.timestamp)
            trades.extend(tp_sl_trades)

            # Update equity after TP/SL
            account.update_equity(prices)

            # Determine trigger symbol
            trigger_symbol = trigger.symbol if trigger.symbol else config.symbols[0]

            # Build MarketData for strategy (pass trades for recent_trades)
            market_data = self._build_market_data(
                account, data_provider, trigger, trigger_symbol, trades
            )

            # Execute strategy
            result = executor.execute(config.code, market_data, {})

            if result.success and result.decision:
                decision = result.decision
                symbol = decision.symbol or trigger_symbol
                current_price = prices.get(symbol, 0)

                if current_price > 0:
                    # Get signal names for logging
                    signal_names = [
                        s.get("signal_name", "") for s in (trigger.triggered_signals or [])
                    ]

                    trade = simulator.execute_decision(
                        decision=decision,
                        account=account,
                        current_price=current_price,
                        timestamp=trigger.timestamp,
                        trigger_type=trigger.trigger_type,
                        pool_name=trigger.pool_name,
                        triggered_signals=signal_names,
                    )
                    if trade:
                        trades.append(trade)

            # Update equity and record
            account.update_equity(prices)
            equity_curve.append({
                "timestamp": trigger.timestamp,
                "equity": account.equity,
                "balance": account.balance,
                "drawdown": account.max_drawdown,
            })

            return trigger.timestamp

        # Process signal triggers with dynamic scheduled triggers
        for signal_trigger in signal_triggers:
            # Before processing this signal, check if scheduled triggers should fire
            if scheduled_interval_ms:
                next_scheduled_time = last_trigger_time + scheduled_interval_ms
                while next_scheduled_time < signal_trigger.timestamp:
                    # Fire scheduled trigger
                    scheduled_trigger = TriggerEvent(
                        timestamp=next_scheduled_time,
                        trigger_type="scheduled",
                        symbol="",
                    )
                    last_trigger_time = execute_trigger(scheduled_trigger)
                    next_scheduled_time = last_trigger_time + scheduled_interval_ms

            # Process signal trigger (resets scheduled timer)
            last_trigger_time = execute_trigger(signal_trigger)

        # After all signal triggers, continue with remaining scheduled triggers until end_time
        if scheduled_interval_ms:
            next_scheduled_time = last_trigger_time + scheduled_interval_ms
            while next_scheduled_time <= config.end_time_ms:
                scheduled_trigger = TriggerEvent(
                    timestamp=next_scheduled_time,
                    trigger_type="scheduled",
                    symbol="",
                )
                last_trigger_time = execute_trigger(scheduled_trigger)
                next_scheduled_time = last_trigger_time + scheduled_interval_ms

        # Log final trigger counts
        signal_count = sum(1 for t in all_triggers if t.trigger_type == "signal")
        scheduled_count = sum(1 for t in all_triggers if t.trigger_type == "scheduled")
        logger.info(f"Executed {len(all_triggers)} triggers "
                   f"({signal_count} signal, {scheduled_count} scheduled)")

        backtest_thread_pool.shutdown(wait=False)
        return trades, equity_curve, all_triggers

    def run_event_loop_generator(
        self,
        config: BacktestConfig,
        signal_triggers: List[TriggerEvent],
        account: VirtualAccount,
        simulator: ExecutionSimulator,
        data_provider: HistoricalDataProvider,
    ):
        """
        Generator version of event loop for streaming progress.

        Yields TriggerExecutionResult for each trigger (signal or scheduled).
        Handles dynamic scheduled trigger generation with timer reset.
        """
        from program_trader.executor import SandboxExecutor
        from concurrent.futures import ThreadPoolExecutor

        backtest_thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backtest")
        executor = SandboxExecutor(timeout_seconds=5, thread_pool=backtest_thread_pool)

        try:
            yield from self._run_generator_body(
                config, signal_triggers, account, simulator, data_provider, executor
            )
        finally:
            backtest_thread_pool.shutdown(wait=False)

    def _run_generator_body(
        self,
        config: BacktestConfig,
        signal_triggers: List[TriggerEvent],
        account: VirtualAccount,
        simulator: ExecutionSimulator,
        data_provider: HistoricalDataProvider,
        executor,
    ):
        """Inner generator body for run_event_loop_generator."""
        all_trades: List[BacktestTradeRecord] = []

        # Scheduled trigger state - now uses seconds directly
        scheduled_interval_ms = None
        if config.scheduled_interval_sec:
            scheduled_interval_ms = config.scheduled_interval_sec * 1000

        last_trigger_time = config.start_time_ms

        def check_tp_sl_between_triggers(
            last_time_ms: int,
            current_time_ms: int,
        ) -> List[BacktestTradeRecord]:
            """Check TP/SL using 1m kline high/low for maximum accuracy."""
            all_tp_sl_trades = []

            # Get 1m klines between triggers for each symbol with positions
            for symbol in config.symbols:
                pos = account.get_position(symbol)
                if not pos:
                    continue

                # Use 1m klines for precise TP/SL detection
                klines = data_provider.get_klines_between(
                    symbol, last_time_ms, current_time_ms, "1m"
                )

                if klines:
                    trades = simulator.check_tp_sl_with_klines(
                        account, klines, pos.side, data_provider
                    )
                    all_tp_sl_trades.extend(trades)

            # Sort by exit timestamp
            all_tp_sl_trades.sort(key=lambda t: t.exit_timestamp or 0)
            return all_tp_sl_trades

        def execute_single_trigger(
            trigger: TriggerEvent,
            prev_trigger_time: int,
        ) -> TriggerExecutionResult:
            """Execute a single trigger and return result."""
            equity_before = account.equity

            # Set current time and clear query log
            data_provider.set_current_time(trigger.timestamp)
            data_provider.clear_query_log()

            # Get current prices
            prices = data_provider.get_current_prices(config.symbols)
            if not prices:
                return TriggerExecutionResult(
                    trigger=trigger,
                    trigger_symbol=config.symbols[0] if config.symbols else "",
                    prices={},
                    executor_result=None,
                    trade=None,
                    tp_sl_trades=[],
                    equity_before=equity_before,
                    equity_after=equity_before,
                    equity_after_tp_sl=equity_before,
                    unrealized_pnl=0,
                    data_queries=[],
                )

            # Check TP/SL using kline high/low between triggers (more accurate)
            tp_sl_trades = check_tp_sl_between_triggers(prev_trigger_time, trigger.timestamp)

            # Update equity after TP/SL and record it
            account.update_equity(prices)
            equity_after_tp_sl = account.equity

            # Determine trigger symbol
            trigger_symbol = trigger.symbol if trigger.symbol else config.symbols[0]

            # Snapshot account state BEFORE strategy execution (for logging)
            balance_before = account.balance
            positions_before = {
                k: {
                    "side": v.side,
                    "size": v.size,
                    "entry_price": v.entry_price,
                    "opened_at": v.entry_timestamp,
                }
                for k, v in account.positions.items()
            }
            used_margin_before = account.get_used_margin()
            margin_usage_percent_before = account.get_margin_usage_percent()

            # Build MarketData for strategy (pass all_trades for recent_trades)
            market_data = self._build_market_data(
                account, data_provider, trigger, trigger_symbol, all_trades
            )

            # Execute strategy
            result = executor.execute(config.code, market_data, {})

            trade = None
            if result.success and result.decision:
                decision = result.decision
                symbol = decision.symbol or trigger_symbol
                current_price = prices.get(symbol, 0)

                if current_price > 0 and decision.operation != "hold":
                    signal_names = [
                        s.get("signal_name", "") for s in (trigger.triggered_signals or [])
                    ]
                    trade = simulator.execute_decision(
                        decision=decision,
                        account=account,
                        current_price=current_price,
                        timestamp=trigger.timestamp,
                        trigger_type=trigger.trigger_type,
                        pool_name=trigger.pool_name,
                        triggered_signals=signal_names,
                    )
                    if trade:
                        all_trades.append(trade)

            # Track TP/SL trades
            for tp_sl_trade in tp_sl_trades:
                all_trades.append(tp_sl_trade)

            # Update equity
            account.update_equity(prices)

            return TriggerExecutionResult(
                trigger=trigger,
                trigger_symbol=trigger_symbol,
                prices=prices,
                executor_result=result,
                trade=trade,
                tp_sl_trades=tp_sl_trades,
                equity_before=equity_before,
                equity_after=account.equity,
                equity_after_tp_sl=equity_after_tp_sl,
                unrealized_pnl=account.unrealized_pnl_total,
                balance_before=balance_before,
                positions_before=positions_before,
                used_margin_before=used_margin_before,
                margin_usage_percent_before=margin_usage_percent_before,
                data_queries=data_provider.get_query_log(),
            )

        # Process signal triggers with dynamic scheduled triggers
        for signal_trigger in signal_triggers:
            # Before processing this signal, fire any pending scheduled triggers
            if scheduled_interval_ms:
                next_scheduled_time = last_trigger_time + scheduled_interval_ms
                while next_scheduled_time < signal_trigger.timestamp:
                    scheduled_trigger = TriggerEvent(
                        timestamp=next_scheduled_time,
                        trigger_type="scheduled",
                        symbol="",
                    )
                    exec_result = execute_single_trigger(scheduled_trigger, last_trigger_time)
                    last_trigger_time = scheduled_trigger.timestamp
                    yield exec_result
                    next_scheduled_time = last_trigger_time + scheduled_interval_ms

            # Process signal trigger (resets scheduled timer)
            exec_result = execute_single_trigger(signal_trigger, last_trigger_time)
            last_trigger_time = signal_trigger.timestamp
            yield exec_result

        # After all signal triggers, continue with remaining scheduled triggers
        if scheduled_interval_ms:
            next_scheduled_time = last_trigger_time + scheduled_interval_ms
            while next_scheduled_time <= config.end_time_ms:
                scheduled_trigger = TriggerEvent(
                    timestamp=next_scheduled_time,
                    trigger_type="scheduled",
                    symbol="",
                )
                exec_result = execute_single_trigger(scheduled_trigger, last_trigger_time)
                last_trigger_time = scheduled_trigger.timestamp
                yield exec_result
                next_scheduled_time = last_trigger_time + scheduled_interval_ms
