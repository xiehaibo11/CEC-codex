from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, index=True)  # Removed unique constraint to allow copies
    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    template_text = Column(Text, nullable=False)
    system_template_text = Column(Text, nullable=False)

    # User-level template support
    is_system = Column(String(10), nullable=False, default="false")  # System templates cannot be deleted
    is_deleted = Column(String(10), nullable=False, default="false")  # Soft delete
    deleted_at = Column(TIMESTAMP, nullable=True)  # When soft-deleted
    created_by = Column(String(100), nullable=False, default="system")  # Creator identifier

    updated_by = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    account_bindings = relationship(
        "AccountPromptBinding",
        back_populates="prompt_template",
        cascade="all, delete-orphan",
    )


class AccountPromptBinding(Base):
    __tablename__ = "account_prompt_bindings"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, unique=True)
    prompt_template_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=False)
    updated_by = Column(String(100), nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))
    deleted_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    account = relationship("Account", back_populates="prompt_binding")
    prompt_template = relationship("PromptTemplate", back_populates="account_bindings")


class PromptBacktestTask(Base):
    """Prompt backtest task - batch test prompt modifications against historical decisions"""
    __tablename__ = "prompt_backtest_tasks"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    wallet_address = Column(String(100), nullable=True, index=True)
    environment = Column(String(20), nullable=True)  # testnet/mainnet
    name = Column(String(200), nullable=True)  # User-defined task name
    status = Column(String(20), nullable=False, default="pending")  # pending/running/completed/failed
    total_count = Column(Integer, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    replace_rules = Column(Text, nullable=True)  # JSON: replacement rules used
    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    # Relationships
    account = relationship("Account")
    items = relationship("PromptBacktestItem", back_populates="task", cascade="all, delete-orphan")


class PromptBacktestItem(Base):
    """Individual item in a prompt backtest task"""
    __tablename__ = "prompt_backtest_items"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("prompt_backtest_tasks.id"), nullable=False, index=True)
    original_decision_log_id = Column(Integer, ForeignKey("ai_decision_logs.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending/running/completed/failed
    error_message = Column(Text, nullable=True)

    # Original data snapshot
    original_operation = Column(String(20), nullable=True)
    original_symbol = Column(String(20), nullable=True)
    original_target_portion = Column(DECIMAL(10, 6), nullable=True)
    original_reasoning = Column(Text, nullable=True)
    original_decision_json = Column(Text, nullable=True)
    original_realized_pnl = Column(DECIMAL(18, 6), nullable=True)
    original_decision_time = Column(TIMESTAMP, nullable=True)
    original_prompt_template_name = Column(String(200), nullable=True)

    # Modified prompt (cache)
    modified_prompt = Column(Text, nullable=True)

    # New decision results
    new_operation = Column(String(20), nullable=True)
    new_symbol = Column(String(20), nullable=True)
    new_target_portion = Column(DECIMAL(10, 6), nullable=True)
    new_reasoning = Column(Text, nullable=True)
    new_decision_json = Column(Text, nullable=True)

    # Derived fields
    decision_changed = Column(Boolean, nullable=True)
    change_type = Column(String(50), nullable=True)  # e.g., buy_to_hold
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    task = relationship("PromptBacktestTask", back_populates="items")
    original_decision_log = relationship("AIDecisionLog")
