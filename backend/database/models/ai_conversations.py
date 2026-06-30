from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class KlineAIAnalysisLog(Base):
    """Store K-line AI analysis logs for chart insights"""
    __tablename__ = "kline_ai_analysis_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)

    # Analysis context
    symbol = Column(String(20), nullable=False, index=True)
    period = Column(String(10), nullable=False)  # K-line period (1m, 5m, 1h, etc.)
    user_message = Column(Text, nullable=True)  # User's custom question

    # AI model info
    model_used = Column(String(100), nullable=False)

    # Snapshots
    prompt_snapshot = Column(Text, nullable=True)  # Full prompt sent to AI
    analysis_result = Column(Text, nullable=True)  # AI's analysis response (Markdown)

    # Metadata
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Relationships
    user = relationship("User")
    account = relationship("Account")


class AiPromptConversation(Base):
    """AI Prompt Generation Conversation Sessions"""
    __tablename__ = "ai_prompt_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    prompt_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False, default="New Strategy Prompt")
    compression_points = Column(Text, nullable=True)  # JSON array of compression records
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User")
    prompt_template = relationship("PromptTemplate")
    messages = relationship(
        "AiPromptMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AiPromptMessage.created_at"
    )


class AiPromptMessage(Base):
    """Messages in AI Prompt Generation Conversations"""
    __tablename__ = "ai_prompt_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_prompt_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # Message content (markdown)

    # For assistant messages: extracted prompt from ```prompt``` code block
    prompt_result = Column(Text, nullable=True)

    # Reasoning and tool call logs (aligned with AiProgramMessage)
    reasoning_snapshot = Column(Text, nullable=True)  # AI reasoning process (thinking)
    tool_calls_log = Column(Text, nullable=True)  # JSON: tool calls and results

    # Completion status for retry/continue functionality
    is_complete = Column(Boolean, default=True)  # False = interrupted, can retry
    interrupt_reason = Column(Text, nullable=True)  # Reason for interruption (API error, timeout, etc.)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Relationships
    conversation = relationship("AiPromptConversation", back_populates="messages")


class AiSignalConversation(Base):
    """AI Signal Creation Conversation Sessions"""
    __tablename__ = "ai_signal_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False, default="New Signal")
    compression_points = Column(Text, nullable=True)  # JSON array of compression records
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User")
    messages = relationship(
        "AiSignalMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AiSignalMessage.created_at"
    )


class AiSignalMessage(Base):
    """Messages in AI Signal Creation Conversations"""
    __tablename__ = "ai_signal_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_signal_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # Message content (markdown)

    # For assistant messages: extracted signal configs from ```signal-config``` code blocks
    signal_configs = Column(Text, nullable=True)  # JSON array of signal configurations

    # Reasoning and tool call logs (aligned with other AI assistants)
    reasoning_snapshot = Column(Text, nullable=True)  # AI reasoning process (thinking)
    tool_calls_log = Column(Text, nullable=True)  # JSON: tool calls and results
    is_complete = Column(Boolean, nullable=True, default=True)  # False if interrupted
    interrupt_reason = Column(Text, nullable=True)  # API error, timeout, user cancel, etc.

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Relationships
    conversation = relationship("AiSignalConversation", back_populates="messages")


class AiAttributionConversation(Base):
    """AI Attribution Analysis Conversation Sessions"""
    __tablename__ = "ai_attribution_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False, default="New Analysis")
    compression_points = Column(Text, nullable=True)  # JSON array of compression records
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User")
    messages = relationship(
        "AiAttributionMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AiAttributionMessage.created_at"
    )


class AiAttributionMessage(Base):
    """Messages in AI Attribution Analysis Conversations"""
    __tablename__ = "ai_attribution_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_attribution_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # Message content (markdown)

    # For assistant messages: extracted diagnosis results from AI analysis
    diagnosis_result = Column(Text, nullable=True)  # JSON: diagnosis cards and prompt suggestions

    # Reasoning and tool call logs (aligned with other AI assistants)
    reasoning_snapshot = Column(Text, nullable=True)  # AI reasoning process
    tool_calls_log = Column(Text, nullable=True)  # JSON: tool calls and results log
    is_complete = Column(Boolean, nullable=True, default=True)  # False if interrupted
    interrupt_reason = Column(Text, nullable=True)  # API error, timeout, user cancel, etc.

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Relationships
    conversation = relationship("AiAttributionConversation", back_populates="messages")


class AiProgramConversation(Base):
    """AI Program Coding Conversation Sessions"""
    __tablename__ = "ai_program_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("trading_programs.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False, default="New Program")
    compression_points = Column(Text, nullable=True)  # JSON array of compression records
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User")
    program = relationship("TradingProgram")
    messages = relationship(
        "AiProgramMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AiProgramMessage.created_at"
    )


class AiProgramMessage(Base):
    """Messages in AI Program Coding Conversations"""
    __tablename__ = "ai_program_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_program_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # Message content (markdown)

    # For assistant messages: code suggestion that needs user confirmation
    code_suggestion = Column(Text, nullable=True)  # Python code to save (requires user confirm)

    # Reasoning and tool call logs
    reasoning_snapshot = Column(Text, nullable=True)  # AI reasoning process (thinking)
    tool_calls_log = Column(Text, nullable=True)  # JSON: tool calls and results

    # Completion status for retry/continue functionality
    is_complete = Column(Boolean, default=True)  # False = interrupted, can retry
    interrupt_reason = Column(Text, nullable=True)  # Reason for interruption (API error, timeout, etc.)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Relationships
    conversation = relationship("AiProgramConversation", back_populates="messages")
