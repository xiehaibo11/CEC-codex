from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class TradingProgram(Base):
    """Trading program (reusable strategy code template)"""
    __tablename__ = "trading_programs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Program definition
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    code = Column(Text, nullable=False)  # Python strategy code
    params = Column(Text, nullable=True)  # JSON: default parameters
    icon = Column(String(50), nullable=True)  # Icon identifier for UI

    # Backtest results cache
    last_backtest_result = Column(Text, nullable=True)  # JSON
    last_backtest_at = Column(TIMESTAMP, nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))
    deleted_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User")
    bindings = relationship("AccountProgramBinding", back_populates="program")
    execution_logs = relationship("ProgramExecutionLog", back_populates="program", passive_deletes=True)


class AccountProgramBinding(Base):
    """Binding between AI Trader (Account) and Trading Program with trigger config"""
    __tablename__ = "account_program_bindings"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("trading_programs.id"), nullable=False, index=True)

    # Trigger configuration
    signal_pool_ids = Column(Text, nullable=True)  # JSON: [1, 2, 3]
    trigger_interval = Column(Integer, nullable=False, default=300)  # seconds
    scheduled_trigger_enabled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_trigger_at = Column(TIMESTAMP, nullable=True)

    # Custom params override (optional, overrides program.params)
    params_override = Column(Text, nullable=True)  # JSON

    # Exchange selection for this binding (hyperliquid or binance)
    exchange = Column(String(20), nullable=False, default="hyperliquid")

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))
    deleted_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    account = relationship("Account")
    program = relationship("TradingProgram", back_populates="bindings")
    execution_logs = relationship("ProgramExecutionLog", back_populates="binding")


class ProgramExecutionLog(Base):
    """Execution log for trading programs"""
    __tablename__ = "program_execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    binding_id = Column(Integer, ForeignKey("account_program_bindings.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("trading_programs.id", ondelete="SET NULL"), nullable=True, index=True)
    program_name = Column(String(200), nullable=True)  # Stored for history when program is deleted

    # Trigger info
    trigger_type = Column(String(20), nullable=False)  # "signal" or "scheduled"
    trigger_symbol = Column(String(20), nullable=True)
    signal_pool_id = Column(Integer, nullable=True)  # Which signal pool triggered
    wallet_address = Column(String(100), nullable=True)  # Which wallet was used

    # Execution result
    success = Column(Boolean, nullable=False)
    decision_action = Column(String(20), nullable=True)  # buy/sell/close/hold
    decision_symbol = Column(String(20), nullable=True)
    decision_size_usd = Column(Float, nullable=True)
    decision_leverage = Column(Integer, nullable=True)
    decision_reason = Column(Text, nullable=True)
    decision_json = Column(Text, nullable=True)  # Full decision as JSON
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Float, nullable=True)

    # Context snapshots for analysis/backtest
    market_context = Column(Text, nullable=True)  # JSON: market data at execution time
    params_snapshot = Column(Text, nullable=True)  # JSON: params used for this execution

    # Order tracking for Completed Trades integration
    # NOTE: hyperliquid_order_id is used as exchange_order_id for attribution analysis
    # It stores order IDs from any exchange (Hyperliquid, Binance, etc.), not just Hyperliquid
    hyperliquid_order_id = Column(String(100), nullable=True, index=True)  # Main order ID (exchange-agnostic)
    tp_order_id = Column(String(100), nullable=True)  # Take profit order ID
    sl_order_id = Column(String(100), nullable=True)  # Stop loss order ID

    # Environment and PnL tracking (for attribution analysis)
    environment = Column(String(20), nullable=True, index=True)  # "testnet" | "mainnet"
    realized_pnl = Column(DECIMAL(18, 6), nullable=True)  # Realized PnL (filled on user refresh)
    pnl_updated_at = Column(TIMESTAMP, nullable=True)  # When PnL was last updated

    # Exchange identifier: "hyperliquid" or "binance"
    # NULL for historical data, treated as "hyperliquid" for backward compatibility
    exchange = Column(String(20), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Relationships
    binding = relationship("AccountProgramBinding", back_populates="execution_logs")
    account = relationship("Account")
    program = relationship("TradingProgram")


class BacktestResult(Base):
    """
    Stores backtest results for both Program and Prompt (future) backtests.
    """
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    backtest_type = Column(String(20), nullable=False, default="program")  # "program" | "prompt"
    binding_id = Column(Integer, ForeignKey("account_program_bindings.id"), nullable=True)
    prompt_id = Column(Integer, nullable=True)  # For future prompt backtest
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Configuration
    config = Column(Text, nullable=True)  # JSON: full config snapshot

    # Time range
    start_time = Column(TIMESTAMP, nullable=True)
    end_time = Column(TIMESTAMP, nullable=True)

    # Results
    initial_balance = Column(Float, default=10000)
    final_equity = Column(Float, nullable=True)
    total_pnl = Column(Float, default=0)
    total_pnl_percent = Column(Float, default=0)
    max_drawdown = Column(Float, default=0)
    max_drawdown_percent = Column(Float, default=0)

    # Statistics
    total_triggers = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0)
    profit_factor = Column(Float, default=0)
    sharpe_ratio = Column(Float, nullable=True)

    # Equity curve (JSON array)
    equity_curve = Column(Text, nullable=True)

    # Execution info
    execution_time_ms = Column(Integer, nullable=True)
    status = Column(String(20), default="running")  # "running" | "completed" | "error"
    error_message = Column(Text, nullable=True)

    # Exchange used for data source: "hyperliquid" or "binance"
    # NULL for historical data, treated as "hyperliquid" for backward compatibility
    exchange = Column(String(20), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    completed_at = Column(TIMESTAMP, nullable=True)

    # Relationships
    trigger_logs = relationship("BacktestTriggerLog", back_populates="backtest", cascade="all, delete-orphan")


class BacktestTriggerLog(Base):
    """
    Stores detailed logs for each trigger during backtest.
    Supports both Program decisions and AI decisions (future).
    """
    __tablename__ = "backtest_trigger_logs"

    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, ForeignKey("backtest_results.id", ondelete="CASCADE"), nullable=False)
    trigger_index = Column(Integer, nullable=False)

    # Trigger info
    trigger_type = Column(String(20), nullable=True)  # "signal" | "scheduled"
    trigger_time = Column(TIMESTAMP, nullable=True)
    symbol = Column(String(20), nullable=True)

    # Decision info
    decision_type = Column(String(20), default="program")  # "program" | "ai"
    decision_action = Column(String(20), nullable=True)  # "open_long" | "close" | "hold" | etc.
    decision_symbol = Column(String(20), nullable=True)
    decision_side = Column(String(10), nullable=True)  # "long" | "short"
    decision_size = Column(Float, nullable=True)
    decision_reason = Column(Text, nullable=True)

    # Trade result
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    fee = Column(Float, nullable=True)  # Trading fee for this trigger
    unrealized_pnl = Column(Float, nullable=True)  # Current unrealized PnL
    realized_pnl = Column(Float, nullable=True)  # Realized PnL from this trade

    # Equity tracking
    equity_before = Column(Float, nullable=True)
    equity_after = Column(Float, nullable=True)

    # Full snapshots (JSON)
    decision_input = Column(Text, nullable=True)  # MarketData snapshot
    decision_output = Column(Text, nullable=True)  # Full decision result
    data_queries = Column(Text, nullable=True)  # Data queries during execution (JSON)
    execution_logs = Column(Text, nullable=True)  # log() outputs during execution (JSON)

    # Error tracking
    execution_error = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    backtest = relationship("BacktestResult", back_populates="trigger_logs")
