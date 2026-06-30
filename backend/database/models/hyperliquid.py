from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class HyperliquidWallet(Base):
    """Store Hyperliquid wallet configurations per AI Trader per environment

    One-to-many relationship with Account. Each AI Trader can have multiple wallets
    (one for testnet, one for mainnet).
    """
    __tablename__ = "hyperliquid_wallets"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)

    # Environment (testnet or mainnet)
    environment = Column(String(20), nullable=False)  # 'testnet' or 'mainnet'

    # Wallet credentials (encrypted)
    private_key_encrypted = Column(String(500), nullable=False)
    wallet_address = Column(String(100), nullable=False, index=True)  # Parsed from private key

    # Trading configuration
    max_leverage = Column(Integer, nullable=False, default=3)  # Maximum allowed leverage (1-50)
    default_leverage = Column(Integer, nullable=False, default=1)  # Default leverage for new orders

    # Agent Wallet support
    key_type = Column(String(20), nullable=False, default="private_key")  # "private_key" or "agent_key"
    master_wallet_address = Column(String(100), nullable=True)  # Required for agent_key mode (query balance/positions)
    agent_valid_until = Column(TIMESTAMP, nullable=True)  # Agent key expiration time

    # Status
    is_active = Column(String(10), nullable=False, default="true")

    # Metadata
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Unique constraint: one wallet per account per environment
    __table_args__ = (
        UniqueConstraint('account_id', 'environment', name='uq_hyperliquid_wallets_account_environment'),
    )

    # Relationships
    account = relationship("Account")


class HyperliquidAccountSnapshot(Base):
    """Store Hyperliquid account state snapshots for audit and analysis"""
    __tablename__ = "hyperliquid_account_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    environment = Column(String(20), nullable=False, index=True)  # "testnet" | "mainnet"
    wallet_address = Column(String(100), nullable=True, index=True)
    snapshot_time = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Account state
    total_equity = Column(DECIMAL(18, 6), nullable=False)
    available_balance = Column(DECIMAL(18, 6), nullable=False)
    used_margin = Column(DECIMAL(18, 6), nullable=False)
    maintenance_margin = Column(DECIMAL(18, 6), nullable=False)

    # Snapshot metadata
    trigger_event = Column(String(50), nullable=True)  # "pre_decision", "post_order", etc.
    snapshot_data = Column(Text, nullable=True)  # JSON of full API response

    account = relationship("Account")


class HyperliquidPosition(Base):
    """Store Hyperliquid position snapshots"""
    __tablename__ = "hyperliquid_positions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    environment = Column(String(20), nullable=False, index=True)  # "testnet" | "mainnet"
    wallet_address = Column(String(100), nullable=True, index=True)
    snapshot_time = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    symbol = Column(String(20), nullable=False)
    position_size = Column(DECIMAL(18, 8), nullable=False)  # Signed: positive=long, negative=short
    entry_price = Column(DECIMAL(18, 6), nullable=False)
    current_price = Column(DECIMAL(18, 6), nullable=False)
    position_value = Column(DECIMAL(18, 6), nullable=False)
    unrealized_pnl = Column(DECIMAL(18, 6), nullable=False)
    margin_used = Column(DECIMAL(18, 6), nullable=False)
    liquidation_price = Column(DECIMAL(18, 6), nullable=True)
    leverage = Column(Integer, nullable=False)

    # Link to order that created/modified this position
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    account = relationship("Account")
    order = relationship("Order")


class HyperliquidExchangeAction(Base):
    """Track every POST /exchange action for Hyperliquid accounts"""
    __tablename__ = "hyperliquid_exchange_actions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    environment = Column(String(20), nullable=False, index=True)
    wallet_address = Column(String(100), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # e.g., create_order, set_leverage
    status = Column(String(20), nullable=False, default="success")  # success | error
    symbol = Column(String(20), nullable=True)
    side = Column(String(10), nullable=True)
    leverage = Column(Integer, nullable=True)
    size = Column(DECIMAL(24, 12), nullable=True)
    price = Column(DECIMAL(18, 6), nullable=True)
    notional = Column(DECIMAL(26, 10), nullable=True)
    request_weight = Column(Integer, nullable=False, default=1)
    request_payload = Column(Text, nullable=True)
    response_payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    account = relationship("Account")


class HyperliquidBackfillTask(Base):
    """Store Hyperliquid K-line backfill task status"""
    __tablename__ = "hyperliquid_backfill_tasks"

    id = Column(Integer, primary_key=True, index=True)
    symbols = Column(String(200), nullable=False)  # Comma-separated symbols
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
