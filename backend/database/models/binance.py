from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class BinanceWallet(Base):
    """Store Binance Futures API credentials per AI Trader per environment"""
    __tablename__ = "binance_wallets"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    environment = Column(String(20), nullable=False)  # 'testnet' or 'mainnet'
    api_key_encrypted = Column(String(500), nullable=False)
    secret_key_encrypted = Column(String(500), nullable=False)
    max_leverage = Column(Integer, nullable=False, default=20)
    default_leverage = Column(Integer, nullable=False, default=1)
    is_active = Column(String(10), nullable=False, default="true")
    # Binance API broker rebate eligibility status (mainnet only)
    # True: eligible for rebate, False: not eligible (daily quota limit applies)
    rebate_working = Column(Boolean, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    __table_args__ = (
        UniqueConstraint('account_id', 'environment', name='uq_binance_wallets_account_environment'),
    )

    account = relationship("Account")


class BinanceAccountSnapshot(Base):
    """Store Binance account state snapshots"""
    __tablename__ = "binance_account_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    environment = Column(String(20), nullable=False, index=True)
    snapshot_time = Column(TIMESTAMP, server_default=func.current_timestamp())
    total_wallet_balance = Column(DECIMAL(18, 6), nullable=False)
    available_balance = Column(DECIMAL(18, 6), nullable=False)
    total_unrealized_profit = Column(DECIMAL(18, 6), nullable=False)
    total_margin_balance = Column(DECIMAL(18, 6), nullable=False)
    total_initial_margin = Column(DECIMAL(18, 6), nullable=True)
    total_maint_margin = Column(DECIMAL(18, 6), nullable=True)
    trigger_event = Column(String(50), nullable=True)
    snapshot_data = Column(Text, nullable=True)

    account = relationship("Account")


class BinanceBackfillTask(Base):
    """Store Binance data backfill task status"""
    __tablename__ = "binance_backfill_tasks"

    id = Column(Integer, primary_key=True, index=True)
    symbols = Column(String(200), nullable=False)  # Comma-separated symbols
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
