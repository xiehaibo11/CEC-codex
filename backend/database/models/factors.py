from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class FactorValue(Base):
    """Computed factor values for each symbol/period/timestamp"""
    __tablename__ = "factor_values"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid")
    symbol = Column(String(20), nullable=False)
    period = Column(String(10), nullable=False)
    factor_name = Column(String(80), nullable=False)
    factor_category = Column(String(30), nullable=False)
    timestamp = Column(Integer, nullable=False)  # Unix seconds
    value = Column(Float, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'period', 'factor_name', 'timestamp',
                         name='factor_values_unique_key'),
    )


class FactorEffectiveness(Base):
    """Factor effectiveness metrics (IC, ICIR, win rate, etc.)"""
    __tablename__ = "factor_effectiveness"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid")
    factor_name = Column(String(80), nullable=False)
    factor_category = Column(String(30), nullable=False)
    symbol = Column(String(20), nullable=False)
    period = Column(String(10), nullable=False)
    forward_period = Column(String(10), nullable=False)
    calc_date = Column(Date, nullable=False)
    lookback_days = Column(Integer, nullable=False, default=30)
    ic_mean = Column(Float, nullable=True)
    ic_std = Column(Float, nullable=True)
    icir = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    decay_half_life = Column(Integer, nullable=True)
    sample_count = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('exchange', 'factor_name', 'symbol', 'period', 'forward_period', 'calc_date',
                         name='factor_effectiveness_unique_key'),
    )


class CustomFactor(Base):
    """User/AI-defined custom factor expressions"""
    __tablename__ = "custom_factors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    expression = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(30), nullable=False, default="custom")
    source = Column(String(20), nullable=False, default="manual")  # manual / ai / builtin
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('name', name='custom_factors_name_unique'),
    )
