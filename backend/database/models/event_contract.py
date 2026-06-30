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
