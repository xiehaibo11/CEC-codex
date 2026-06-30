"""SignalBacktestService class assembled from responsibility mixins."""

from services.signal_backtest_service.entry import BacktestEntryMixin
from services.signal_backtest_service.triggers import TriggerRangeMixin
from services.signal_backtest_service.triggers_extra import TriggerExtraMixin
from services.signal_backtest_service.buckets import BucketComputeMixin
from services.signal_backtest_service.buckets_window import BucketWindowMixin
from services.signal_backtest_service.pool import PoolDispatchMixin
from services.signal_backtest_service.pool_and import PoolAndLogicMixin
from services.signal_backtest_service.pool_or import PoolOrLogicMixin
from services.signal_backtest_service.indicators import IndicatorTimeMixin
from services.signal_backtest_service.indicators_calc import IndicatorCalcMixin


class SignalBacktestService(
    BacktestEntryMixin,
    TriggerRangeMixin,
    TriggerExtraMixin,
    BucketComputeMixin,
    BucketWindowMixin,
    PoolDispatchMixin,
    PoolAndLogicMixin,
    PoolOrLogicMixin,
    IndicatorTimeMixin,
    IndicatorCalcMixin,
):
    """Service for backtesting signals against historical data."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

