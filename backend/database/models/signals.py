from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class SignalDefinition(Base):
    """Signal definitions for market condition triggers"""
    __tablename__ = "signal_definitions"

    id = Column(Integer, primary_key=True, index=True)
    signal_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    trigger_condition = Column(Text, nullable=False)  # JSONB stored as text
    enabled = Column(Boolean, nullable=True, default=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid")

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))
    deleted_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


class SignalPool(Base):
    """Signal pools for grouping multiple signals"""
    __tablename__ = "signal_pools"

    id = Column(Integer, primary_key=True, index=True)
    pool_name = Column(String(100), nullable=False)
    signal_ids = Column(Text, nullable=False, default="[]")  # JSONB stored as text
    symbols = Column(Text, nullable=False, default="[]")  # JSONB stored as text
    logic = Column(String(10), nullable=True, default="OR")  # AND/OR logic
    enabled = Column(Boolean, nullable=True, default=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid")
    source_type = Column(String(30), nullable=False, default="market_signals")
    source_config = Column(Text, nullable=False, default="{}")  # wallet_tracking-only JSON config

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))
    deleted_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class SignalTriggerLog(Base):
    """Logs of signal triggers for audit and analysis"""
    __tablename__ = "signal_trigger_logs"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, nullable=True)
    pool_id = Column(Integer, nullable=True)
    symbol = Column(String(20), nullable=False)
    trigger_value = Column(Text, nullable=True)  # JSONB stored as text
    triggered_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    market_regime = Column(Text, nullable=True)  # JSON: {"regime", "direction", "confidence", "reason"}


class TraderTriggerConfig(Base):
    """Configuration for trader trigger settings"""
    __tablename__ = "trader_trigger_config"

    trader_id = Column(String(36), primary_key=True)  # UUID as string
    scheduled_enabled = Column(Boolean, nullable=True, default=True)
    scheduled_interval = Column(Integer, nullable=True, default=30)
    signal_pool_id = Column(Integer, nullable=True)  # Deprecated: use signal_pool_ids instead
    signal_pool_ids = Column(Text, nullable=True)  # JSON array of signal pool IDs, e.g. "[1, 2, 3]"
    last_trigger_time = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())
