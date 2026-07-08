from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base


CRYPTO_MIN_COMMISSION = 0.1  # $0.1 minimum commission

CRYPTO_COMMISSION_RATE = 0.001  # 0.1% commission rate

CRYPTO_MIN_ORDER_QUANTITY = 1

CRYPTO_LOT_SIZE = 1


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(100), nullable=False, default="v1")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    market = Column(String(10), nullable=False)
    quantity = Column(DECIMAL(18, 8), nullable=False, default=0)  # Support fractional crypto amounts
    available_quantity = Column(DECIMAL(18, 8), nullable=False, default=0)
    avg_cost = Column(DECIMAL(18, 6), nullable=False, default=0)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    account = relationship("Account", back_populates="positions")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        # Serves the hot dashboard/polling query pattern:
        # WHERE account_id = ... AND status = ... (also covers account_id-only lookups).
        Index("ix_orders_account_id_status", "account_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(100), nullable=False, default="v1")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    order_no = Column(String(32), unique=True, nullable=False)
    symbol = Column(String(20), nullable=False)  # e.g., 'BTC/USD'
    name = Column(String(100), nullable=False)   # e.g., 'Bitcoin'
    market = Column(String(10), nullable=False, default="CRYPTO")
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)
    price = Column(DECIMAL(18, 6))
    quantity = Column(DECIMAL(18, 8), nullable=False)  # Support fractional crypto amounts
    filled_quantity = Column(DECIMAL(18, 8), nullable=False, default=0)
    status = Column(String(20), nullable=False)

    # Hyperliquid specific fields
    hyperliquid_environment = Column(String(20), nullable=True)  # "testnet" | "mainnet" | null
    leverage = Column(Integer, nullable=True, default=1)  # Position leverage (1-50)
    margin_mode = Column(String(20), nullable=True, default="cross")  # "cross" or "isolated"
    reduce_only = Column(String(10), nullable=True, default="false")  # Only close positions
    hyperliquid_order_id = Column(String(50), nullable=True)  # OID from Hyperliquid API
    liquidation_price = Column(DECIMAL(18, 6), nullable=True)  # Liquidation price for position

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    account = relationship("Account", back_populates="orders")
    trades = relationship("Trade", back_populates="order")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)  # e.g., 'BTC/USD'
    name = Column(String(100), nullable=False)   # e.g., 'Bitcoin'
    market = Column(String(10), nullable=False, default="CRYPTO")
    side = Column(String(10), nullable=False)
    price = Column(DECIMAL(18, 6), nullable=False)
    quantity = Column(DECIMAL(18, 8), nullable=False)  # Support fractional crypto amounts
    commission = Column(DECIMAL(18, 6), nullable=False, default=0)
    trade_time = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Hyperliquid environment tracking
    hyperliquid_environment = Column(String(20), nullable=True)  # "testnet" | "mainnet" | null (paper)

    order = relationship("Order", back_populates="trades")


class AIDecisionLog(Base):
    __tablename__ = "ai_decision_logs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    decision_time = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    reason = Column(String(1000), nullable=False)  # AI reasoning for the decision
    operation = Column(String(10), nullable=False)  # buy/sell/hold
    symbol = Column(String(20), nullable=True)  # symbol for buy/sell operations
    prev_portion = Column(DECIMAL(10, 6), nullable=False, default=0)  # previous balance portion
    target_portion = Column(DECIMAL(10, 6), nullable=False)  # target balance portion
    total_balance = Column(DECIMAL(18, 2), nullable=False)  # total balance at decision time
    executed = Column(String(10), nullable=False, default="false")  # whether the decision was executed
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)  # linked order if executed
    prompt_snapshot = Column(Text, nullable=True)
    reasoning_snapshot = Column(Text, nullable=True)
    decision_snapshot = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Hyperliquid environment tracking
    hyperliquid_environment = Column(String(20), nullable=True)  # "testnet" | "mainnet" | null (paper)
    wallet_address = Column(String(100), nullable=True, index=True)

    # Decision tracking fields for analysis
    prompt_template_id = Column(Integer, nullable=True, index=True)  # Link to strategy/prompt template OR program
    signal_trigger_id = Column(Integer, nullable=True, index=True)  # Link to signal trigger
    # NOTE: hyperliquid_order_id is used as exchange_order_id for attribution analysis
    # It stores order IDs from any exchange (Hyperliquid, Binance, etc.), not just Hyperliquid
    hyperliquid_order_id = Column(String(100), nullable=True, index=True)  # Main order ID (exchange-agnostic)
    tp_order_id = Column(String(100), nullable=True)  # Take profit order ID
    sl_order_id = Column(String(100), nullable=True)  # Stop loss order ID
    realized_pnl = Column(DECIMAL(18, 6), nullable=True)  # Realized PnL (filled on user refresh)
    pnl_updated_at = Column(TIMESTAMP, nullable=True)  # When PnL was last updated

    # Decision source type: "prompt_template" (AI Trader) or "program" (Program Trader)
    # NULL for old data, treated as "prompt_template" for backward compatibility
    decision_source_type = Column(String(20), nullable=True)

    # Exchange identifier: "hyperliquid" or "binance"
    # NULL for historical data, treated as "hyperliquid" for backward compatibility
    exchange = Column(String(20), nullable=True)
    review_run_id = Column(Integer, nullable=True, index=True)
    review_verdict = Column(String(20), nullable=True)
    review_blocked_reason = Column(Text, nullable=True)

    # Relationships
    account = relationship("Account")
    order = relationship("Order")


class AIReviewRun(Base):
    __tablename__ = "ai_review_runs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    decision_log_id = Column(Integer, ForeignKey("ai_decision_logs.id"), nullable=True, index=True)
    exchange = Column(String(20), nullable=True, index=True)
    environment = Column(String(20), nullable=True, index=True)
    symbol = Column(String(20), nullable=True, index=True)
    operation = Column(String(10), nullable=False)
    original_target_portion = Column(DECIMAL(10, 6), nullable=True)
    original_leverage = Column(Integer, nullable=True)
    verdict = Column(String(20), nullable=False, index=True)
    final_target_portion = Column(DECIMAL(10, 6), nullable=True)
    final_leverage = Column(Integer, nullable=True)
    final_reason = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    account = relationship("Account")
    decision_log = relationship("AIDecisionLog")


class AIReviewAgentReport(Base):
    __tablename__ = "ai_review_agent_reports"

    id = Column(Integer, primary_key=True, index=True)
    review_run_id = Column(Integer, ForeignKey("ai_review_runs.id"), nullable=False, index=True)
    agent_role = Column(String(50), nullable=False, index=True)
    verdict = Column(String(20), nullable=False, index=True)
    confidence = Column(DECIMAL(5, 4), nullable=True)
    report_json = Column(Text, nullable=True)
    report_text = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    review_run = relationship("AIReviewRun")


class AccountAssetSnapshot(Base):
    __tablename__ = "account_asset_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    total_assets = Column(DECIMAL(18, 6), nullable=False)
    cash = Column(DECIMAL(18, 6), nullable=False)
    positions_value = Column(DECIMAL(18, 6), nullable=False)
    trigger_symbol = Column(String(20), nullable=True)
    trigger_market = Column(String(10), nullable=True, default="CRYPTO")
    event_time = Column(TIMESTAMP, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    account = relationship("Account")


class AccountStrategyConfig(Base):
    __tablename__ = "account_strategy_configs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, unique=True)
    price_threshold = Column(Float, nullable=False, default=1.0)  # Deprecated, kept for compatibility
    trigger_interval = Column(Integer, nullable=False, default=150)  # Trigger interval (seconds)
    # Note: Foreign key constraint exists at DB level (via migration), but not in ORM
    # because signal_pools table is managed via raw SQL, not SQLAlchemy models
    signal_pool_id = Column(Integer, nullable=True)  # Deprecated: use signal_pool_ids instead
    signal_pool_ids = Column(Text, nullable=True)  # JSON array of signal pool IDs, e.g. "[1, 2, 3]"
    enabled = Column(String(10), nullable=False, default="true")
    scheduled_trigger_enabled = Column(Boolean, nullable=False, default=True)  # Enable/disable scheduled trigger
    exchange = Column(String(20), nullable=False, default="hyperliquid")  # "hyperliquid" or "binance"
    last_trigger_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    account = relationship("Account")
