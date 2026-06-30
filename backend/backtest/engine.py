"""
Program Backtest Engine

Event-driven backtest engine for Program Trader strategies.
Orchestrates trigger generation, strategy execution, and result calculation.

Responsibilities are split across cohesive mixins:
- TriggerGenerationMixin (engine_triggers.py): signal trigger generation + count estimation.
- EventLoopMixin (engine_event_loop.py): batch + streaming event loops.
- MarketDataBuilderMixin (engine_market_data.py): MarketData construction.
- ResultCalculationMixin (engine_results.py): statistics aggregation.
This module owns the public engine class and top-level run() orchestration.
"""

import logging
import time
from sqlalchemy.orm import Session

from .models import BacktestConfig, BacktestResult
from .virtual_account import VirtualAccount
from .execution_simulator import ExecutionSimulator
from .historical_data_provider import HistoricalDataProvider
from .engine_triggers import TriggerGenerationMixin
from .engine_event_loop import EventLoopMixin
from .engine_market_data import MarketDataBuilderMixin
from .engine_results import ResultCalculationMixin

logger = logging.getLogger(__name__)

# Interval to milliseconds mapping
INTERVAL_MS = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


class ProgramBacktestEngine(
    TriggerGenerationMixin,
    EventLoopMixin,
    MarketDataBuilderMixin,
    ResultCalculationMixin,
):
    """
    Event-driven backtest engine for Program Trader.

    Flow:
    1. Generate trigger events (signal + scheduled)
    2. Sort events by timestamp
    3. For each event:
       - Set historical data provider time
       - Check TP/SL triggers
       - Build MarketData
       - Execute strategy code
       - Simulate order execution
       - Update virtual account
    4. Calculate statistics
    """

    def __init__(self, db: Session):
        self.db = db

    def run(self, config: BacktestConfig) -> BacktestResult:
        """
        Run backtest with given configuration.

        Args:
            config: Backtest configuration

        Returns:
            BacktestResult with statistics and trade history
        """
        start_time = time.time()

        try:
            # 1. Generate signal trigger events (scheduled triggers are dynamic)
            signal_triggers = self._generate_trigger_events(config)

            # Allow backtest even with no signal triggers if scheduled triggers are enabled
            if not signal_triggers and not config.scheduled_interval_sec:
                return BacktestResult(
                    success=False,
                    error="No trigger events generated. Check signal pools and time range."
                )

            # 2. Initialize components
            account = VirtualAccount(initial_balance=config.initial_balance)
            simulator = ExecutionSimulator(
                slippage_percent=config.slippage_percent,
                fee_rate=config.fee_rate,
            )
            data_provider = HistoricalDataProvider(
                db=self.db,
                symbols=config.symbols,
                start_time_ms=config.start_time_ms,
                end_time_ms=config.end_time_ms,
                exchange=config.exchange,
            )

            # 3. Run event loop (returns all triggers including dynamic scheduled ones)
            trades, equity_curve, all_triggers = self._run_event_loop(
                config, signal_triggers, account, simulator, data_provider
            )

            # 4. Calculate statistics
            result = self._calculate_result(
                trades=trades,
                equity_curve=equity_curve,
                triggers=all_triggers,
                account=account,
                config=config,
            )
            result.execution_time_ms = (time.time() - start_time) * 1000

            return result

        except Exception as e:
            logger.error(f"Backtest failed: {e}", exc_info=True)
            return BacktestResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
