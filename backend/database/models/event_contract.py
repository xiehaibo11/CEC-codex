from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class EventContractBacktestRun(Base):
    """5-minute event contract backtest run summary."""
    __tablename__ = "event_contract_backtest_runs"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(20), nullable=False, default="binance", index=True)
    environment = Column(String(20), nullable=False, default="mainnet", index=True)
    period = Column(String(10), nullable=False, default="1m")
    start_time = Column(TIMESTAMP, nullable=False, index=True)
    end_time = Column(TIMESTAMP, nullable=False, index=True)
    config = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    equity_curve = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="completed")
    error_message = Column(Text, nullable=True)
    total_trades = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float, nullable=False, default=0)
    final_equity = Column(Float, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    trade_logs = relationship("EventContractTradeLog", back_populates="run", cascade="all, delete-orphan")


class EventContractTradeLog(Base):
    """Per-trade event contract settlement log."""
    __tablename__ = "event_contract_trade_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("event_contract_backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_index = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(String(10), nullable=False)
    entry_time = Column(TIMESTAMP, nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    expiry_time = Column(TIMESTAMP, nullable=False, index=True)
    expiry_price = Column(Float, nullable=False)
    result = Column(String(10), nullable=False, index=True)
    profit_loss = Column(Float, nullable=False, default=0)
    signal_strength = Column(Float, nullable=True)
    ai_consensus_rate = Column(Float, nullable=True)
    consensus_source = Column(String(30), nullable=True)
    ai_participated = Column(Boolean, nullable=False, default=False)
    ai_model = Column(String(100), nullable=True)
    ai_account_name = Column(String(100), nullable=True)
    signal_time = Column(TIMESTAMP, nullable=True)
    signal_type = Column(String(50), nullable=True)
    event_signal = Column(Text, nullable=True)
    entry_delay_lag_seconds = Column(Integer, nullable=False, default=0)
    expiry_lag_seconds = Column(Integer, nullable=False, default=0)
    long_votes = Column(Integer, nullable=True)
    short_votes = Column(Integer, nullable=True)
    hold_votes = Column(Integer, nullable=True)
    market_state = Column(String(50), nullable=True)
    trap_risk = Column(Float, nullable=True)
    fake_breakout_risk = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    factor_snapshot = Column(Text, nullable=True)
    ai_decision_snapshot = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    run = relationship("EventContractBacktestRun", back_populates="trade_logs")


class EventContractBacktestTask(Base):
    """Persistent task state for long-running event contract backtests."""
    __tablename__ = "event_contract_backtest_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    run_id = Column(Integer, ForeignKey("event_contract_backtest_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(200), nullable=True)
    status = Column(String(30), nullable=False, default="pending", index=True)
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(20), nullable=False, default="binance", index=True)
    environment = Column(String(20), nullable=False, default="mainnet", index=True)
    period = Column(String(10), nullable=False, default="1m")
    config = Column(Text, nullable=True)
    progress_pct = Column(Float, nullable=False, default=0)
    phase = Column(String(60), nullable=True)
    processed_decision_bars = Column(Integer, nullable=False, default=0)
    total_decision_bars = Column(Integer, nullable=False, default=0)
    completed_ai_reviews = Column(Integer, nullable=False, default=0)
    expected_ai_reviews = Column(Integer, nullable=False, default=0)
    ai_reviewer_statuses = Column(Text, nullable=True)
    latest_message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class EventContractPaperTrader(Base):
    """Forward-testing event trader with explicit Paper/Live capability state."""
    __tablename__ = "event_contract_paper_traders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    symbol = Column(String(20), nullable=False, default="BTC", index=True)
    exchange = Column(String(20), nullable=False, default="binance", index=True)
    environment = Column(String(20), nullable=False, default="mainnet", index=True)
    config = Column(Text, nullable=True)  # full strategy config JSON (allowed_utc_hours/platform/...)
    stake_amount = Column(Float, nullable=False, default=100)
    initial_balance = Column(Float, nullable=False, default=10000)
    current_balance = Column(Float, nullable=False, default=10000)
    strategy_fingerprint = Column(String(32), nullable=True, index=True)
    execution_mode = Column(String(10), nullable=False, default="paper")
    leverage = Column(Float, nullable=False, default=10)
    trade_margin = Column(Float, nullable=False, default=100.0)
    max_daily_trades = Column(Integer, nullable=False, default=10)
    profit_target_multiplier = Column(Float, nullable=False, default=2.0)
    last_decision_time = Column(TIMESTAMP, nullable=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    bets = relationship("EventContractPaperBet", back_populates="trader", cascade="all, delete-orphan")


class EventContractPaperBet(Base):
    """A single forward-tested bet placed by a paper trader on live market data."""
    __tablename__ = "event_contract_paper_bets"

    id = Column(Integer, primary_key=True, index=True)
    trader_id = Column(Integer, ForeignKey("event_contract_paper_traders.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="pending_entry", index=True)  # pending_entry|open|settled
    decision_time = Column(TIMESTAMP, nullable=False, index=True)
    entry_time = Column(TIMESTAMP, nullable=True)
    entry_price = Column(Float, nullable=True)
    expiry_time = Column(TIMESTAMP, nullable=True, index=True)
    expiry_price = Column(Float, nullable=True)
    result = Column(String(10), nullable=True)  # win|loss|draw|NULL
    pnl = Column(Float, nullable=True)
    stake = Column(Float, nullable=False)
    payout_ratio = Column(Float, nullable=False)
    market_state = Column(String(50), nullable=True)
    signal_strength = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    analysis_snapshot = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    trader = relationship("EventContractPaperTrader", back_populates="bets")


class EventContractValidationLog(Base):
    """One row per frozen-parameter out-of-sample holdout window, appended by
    the rolling validation scheduler cycle (spec module 4). Cumulative
    significance across ``status='recorded'`` rows for a fingerprint replaces
    manually clicking the holdout endpoint."""
    __tablename__ = "event_contract_validation_log"

    id = Column(Integer, primary_key=True, index=True)
    strategy_fingerprint = Column(String(32), nullable=False, index=True)
    source_run_id = Column(Integer, nullable=True)
    holdout_run_id = Column(Integer, nullable=True, index=True)
    task_id = Column(Integer, nullable=True)
    window_start = Column(TIMESTAMP, nullable=True)
    window_end = Column(TIMESTAMP, nullable=True)
    decided = Column(Integer, nullable=True)
    wins = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending|recorded|failed
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
