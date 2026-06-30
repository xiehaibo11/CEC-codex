from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class User(Base):
    """
    User for authentication and account management
    In this project, use the default user, no user login
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)  # For future password authentication
    is_active = Column(String(10), nullable=False, default="true")
    
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    accounts = relationship("Account", back_populates="user")
    auth_sessions = relationship("UserAuthSession", back_populates="user")
    subscription = relationship("UserSubscription", back_populates="user", uselist=False)


class Account(Base):
    """Trading Account with AI model configuration"""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    version = Column(String(100), nullable=False, default="v1")
    
    # Account Identity
    name = Column(String(100), nullable=False)  # Display name (e.g., "GPT Trader", "Claude Analyst")
    account_type = Column(String(20), nullable=False, default="AI")  # "AI" or "MANUAL"
    is_active = Column(String(10), nullable=False, default="true")
    auto_trading_enabled = Column(String(10), nullable=False, default="true")
    
    # AI Model Configuration (for AI accounts)
    model = Column(String(100), nullable=True, default="gpt-4")  # AI model name
    base_url = Column(String(500), nullable=True, default="https://api.openai.com/v1")  # API endpoint
    api_key = Column(String(500), nullable=True)  # API key for authentication
    
    # Trading Account Balances (USD for CRYPTO market)
    initial_capital = Column(DECIMAL(18, 2), nullable=False, default=10000.00)
    current_cash = Column(DECIMAL(18, 2), nullable=False, default=10000.00)
    frozen_cash = Column(DECIMAL(18, 2), nullable=False, default=0.00)

    # Hyperliquid Trading Configuration
    hyperliquid_enabled = Column(String(10), nullable=False, default="false")
    hyperliquid_environment = Column(String(20), nullable=True)  # "testnet" | "mainnet" | null
    hyperliquid_testnet_private_key = Column(String(500), nullable=True)  # Encrypted storage
    hyperliquid_mainnet_private_key = Column(String(500), nullable=True)  # Encrypted storage
    max_leverage = Column(Integer, nullable=True, default=3)  # Maximum allowed leverage
    default_leverage = Column(Integer, nullable=True, default=1)  # Default leverage for orders

    # Dashboard visibility
    show_on_dashboard = Column(Boolean, nullable=False, default=True)  # Show/hide on Dashboard views

    # Arena View avatar preset (1-12, assigned randomly on creation)
    avatar_preset_id = Column(Integer, nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))
    deleted_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User", back_populates="accounts")
    positions = relationship("Position", back_populates="account")
    orders = relationship("Order", back_populates="account")
    prompt_binding = relationship(
        "AccountPromptBinding",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )


class UserAuthSession(Base):
    __tablename__ = "user_auth_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    user = relationship("User", back_populates="auth_sessions")


class UserSubscription(Base):
    """User subscription for premium features"""
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    subscription_type = Column(String(20), nullable=False, default="free")  # "free" | "premium"
    expires_at = Column(TIMESTAMP, nullable=True)  # NULL for free tier or lifetime premium
    max_sampling_depth = Column(Integer, nullable=False, default=10)  # Free: 10, Premium: up to 60
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationship
    user = relationship("User", back_populates="subscription")


class UserExchangeConfig(Base):
    """Store user exchange selection preferences"""
    __tablename__ = "user_exchange_config"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    selected_exchange = Column(String(20), nullable=False, default="hyperliquid")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User")


class CoinGlassUserKey(Base):
    """Store per-user CoinGlass API credentials."""
    __tablename__ = "coinglass_user_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    api_key_encrypted = Column(Text, nullable=False)
    key_masked = Column(String(32), nullable=True)
    plan_level = Column(String(50), nullable=True)
    expire_time = Column(BigInteger, nullable=True)
    expired = Column(Boolean, nullable=True)
    last_validated_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    user = relationship("User")
