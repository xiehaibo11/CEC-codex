"""Signal Backtest Service.

Backtests signals against historical data to show where triggers would occur.
"""

from services.signal_backtest_service.base import TIMEFRAME_MS, logger
from services.signal_backtest_service.service import SignalBacktestService

# Singleton instance
signal_backtest_service = SignalBacktestService()

__all__ = [
    "TIMEFRAME_MS",
    "logger",
    "SignalBacktestService",
    "signal_backtest_service",
]
