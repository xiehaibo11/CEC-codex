from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(String(500), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class TradingConfig(Base):
    __tablename__ = "trading_configs"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(100), nullable=False, default="v1")
    market = Column(String(10), nullable=False)
    min_commission = Column(Float, nullable=False)
    commission_rate = Column(Float, nullable=False)
    exchange_rate = Column(Float, nullable=False, default=1.0)
    min_order_quantity = Column(Integer, nullable=False, default=1)
    lot_size = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    __table_args__ = (UniqueConstraint('market', 'version'),)


class GlobalSamplingConfig(Base):
    __tablename__ = "global_sampling_configs"

    id = Column(Integer, primary_key=True, index=True)
    sampling_interval = Column(Integer, nullable=False, default=18)  # Sampling interval (seconds)
    sampling_depth = Column(Integer, nullable=False, default=10)  # Sampling pool depth (10-60)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class MarketRegimeConfig(Base):
    """Configuration for Market Regime classification thresholds"""
    __tablename__ = "market_regime_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    is_default = Column(Boolean, nullable=True, default=False)
    rolling_window = Column(Integer, nullable=True, default=48)
    # Breakout thresholds
    breakout_cvd_z = Column(Float, nullable=True, default=1.5)
    breakout_oi_z = Column(Float, nullable=True, default=1.0)
    breakout_price_atr = Column(Float, nullable=True, default=0.5)
    breakout_taker_high = Column(Float, nullable=True, default=1.8)
    breakout_taker_low = Column(Float, nullable=True, default=0.55)
    # Absorption thresholds
    absorption_cvd_z = Column(Float, nullable=True, default=1.5)
    absorption_price_atr = Column(Float, nullable=True, default=0.3)
    # Trap thresholds
    trap_cvd_z = Column(Float, nullable=True, default=1.0)
    trap_oi_z = Column(Float, nullable=True, default=-1.0)
    # Exhaustion thresholds
    exhaustion_cvd_z = Column(Float, nullable=True, default=1.0)
    exhaustion_rsi_high = Column(Float, nullable=True, default=70.0)
    exhaustion_rsi_low = Column(Float, nullable=True, default=30.0)
    # Stop Hunt thresholds
    stop_hunt_range_atr = Column(Float, nullable=True, default=1.0)
    stop_hunt_close_atr = Column(Float, nullable=True, default=0.3)
    # Noise thresholds
    noise_cvd_z = Column(Float, nullable=True, default=0.5)
    # Breakout body ratio (hardcoded 0.4 before, now configurable)
    breakout_body_ratio = Column(Float, nullable=True, default=0.4)
    # Continuation CVD divisor (cvd_weak = cvd_strong / divisor, default 3)
    continuation_cvd_divisor = Column(Float, nullable=True, default=3.0)
    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())
