from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..connection import Base


class HibtWallet(Base):
    """Store HiBT perpetual futures API credentials per AI Trader per environment."""

    __tablename__ = "hibt_wallets"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    environment = Column(String(20), nullable=False)  # 'testnet' or 'mainnet'
    access_key_encrypted = Column(String(500), nullable=False)
    secret_key_encrypted = Column(String(500), nullable=False)
    max_leverage = Column(Integer, nullable=False, default=20)
    default_leverage = Column(Integer, nullable=False, default=1)
    is_active = Column(String(10), nullable=False, default="true")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "environment",
            name="uq_hibt_wallets_account_environment",
        ),
    )

    account = relationship("Account")
