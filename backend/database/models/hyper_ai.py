from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class HyperAiProfile(Base):
    """
    Hyper AI User Profile - Stores user trading preferences and LLM configuration.

    This is the core profile for Hyper AI, containing:
    - Trading style and risk preferences (collected during onboarding)
    - LLM provider configuration (API endpoint, key, model)
    - Onboarding status

    Single-user system: only one profile exists per installation.
    """
    __tablename__ = "hyper_ai_profile"

    id = Column(Integer, primary_key=True, index=True)

    # User identity
    nickname = Column(String(100), nullable=True)  # User's preferred name/nickname

    # Trading preferences (collected during onboarding conversation)
    trading_style = Column(String(50), nullable=True)  # trend_following / mean_reversion / mixed
    risk_preference = Column(String(50), nullable=True)  # conservative / moderate / aggressive
    experience_level = Column(String(50), nullable=True)  # beginner / intermediate / expert
    preferred_symbols = Column(Text, nullable=True)  # JSON array: ["BTC", "ETH", "SOL"]
    preferred_timeframe = Column(String(50), nullable=True)  # short / medium / long
    capital_scale = Column(String(50), nullable=True)  # small / medium / large

    # Onboarding status
    onboarding_completed = Column(Boolean, default=False)  # True after initial setup conversation

    # LLM provider configuration (user selects during onboarding)
    llm_provider = Column(String(50), nullable=True)  # openai / anthropic / google / deepseek / zhipu / minimax / minimax-cn / openrouter / qwen / moonshot / custom
    llm_base_url = Column(String(500), nullable=True)  # API endpoint URL
    llm_api_key_encrypted = Column(Text, nullable=True)  # Encrypted API key (use decrypt_private_key to read)
    llm_model = Column(String(100), nullable=True)  # Model name (e.g., gpt-4o, claude-opus-4-6)

    # Skill System: Controls which Skill modules are active for this user.
    # Skills are SKILL.md files in backend/skills/ that provide domain-specific
    # workflow guidance to Hyper AI (e.g., strategy setup, diagnosis, market analysis).
    # Format: JSON array of enabled skill names, e.g. ["prompt-strategy-setup", "market-analysis"]
    # NULL = all skills enabled (default for new/existing users)
    enabled_skills = Column(Text, nullable=True)

    # External tool configurations (e.g., Tavily web search, future tools)
    # Format: JSON dict keyed by tool name, e.g. {"tavily": {"api_key_encrypted": "...", "enabled": true}}
    # API keys are encrypted using encrypt_private_key() before storage
    tool_configs = Column(Text, nullable=True)

    # Suggested questions for welcome screen (lazy-updated cache)
    # Format: JSON array of 3 questions, e.g. ["How is my BTC Trader doing?", ...]
    # Updated asynchronously when user visits Hyper AI page and cache > 6 hours old
    suggested_questions = Column(Text, nullable=True)
    suggested_questions_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class HyperAiMemory(Base):
    """
    Hyper AI User Memory - Stores AI-extracted insights about the user.

    Memory categories:
    - preference: User preferences (e.g., "likes trend following strategies")
    - decision: User decisions (e.g., "chose 5-minute timeframe for signals")
    - lesson: Trading lessons (e.g., "got caught chasing pumps last time")
    - insight: Strategy insights (e.g., "this strategy underperforms in ranging markets")

    Memory lifecycle:
    - Created: AI extracts from conversations or trade results
    - Updated: AI merges similar memories (Mem0-style deduplication)
    - Soft-deleted: is_active=False when contradicted by newer information
    """
    __tablename__ = "hyper_ai_memory"

    id = Column(Integer, primary_key=True, index=True)

    # Memory content
    category = Column(String(50), nullable=False, index=True)  # preference / decision / lesson / insight
    content = Column(Text, nullable=False)  # The actual memory text

    # Memory metadata
    source = Column(String(50), nullable=True)  # onboarding / prompt_chat / program_chat / signal_chat / trade_result / backtest
    importance = Column(Float, default=0.5)  # 0.0-1.0, higher = more important for retrieval
    is_active = Column(Boolean, default=True)  # False = soft-deleted (contradicted by newer memory)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class HyperAiConversation(Base):
    """
    Hyper AI Conversation Session - Tracks conversation history with compression support.

    Compression mechanism:
    - When token count approaches 70% of context window, compression is triggered
    - AI generates a summary of the conversation
    - Old messages are deleted, summary is stored in this table
    - New messages continue from the compressed state
    """
    __tablename__ = "hyper_ai_conversations"

    id = Column(Integer, primary_key=True, index=True)

    # Conversation metadata
    title = Column(String(200), nullable=False, default="Hyper AI Chat")
    is_onboarding = Column(Boolean, default=False)  # True for onboarding conversations (hidden from history)

    # Compression data
    summary = Column(Text, nullable=True)  # Compressed summary of old messages (after compression)
    compression_points = Column(Text, nullable=True)  # JSON array of compression records
    message_count = Column(Integer, default=0)  # Total messages before compression
    total_tokens = Column(Integer, default=0)  # Estimated total tokens (for compression trigger)

    # Bot integration
    is_bot_conversation = Column(Boolean, default=False)  # True if initiated from Telegram/Discord bot
    bot_platform = Column(String(20), nullable=True)  # telegram / discord

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    compressed_at = Column(TIMESTAMP, nullable=True)  # When compression was performed

    # Relationships
    messages = relationship(
        "HyperAiMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="HyperAiMessage.created_at"
    )


class HyperAiMessage(Base):
    """
    Hyper AI Message - Individual messages in a conversation.

    Stores full message details including:
    - Content and role (user/assistant/system/tool)
    - AI reasoning process (thinking/chain-of-thought)
    - Tool calls and results (function calling)
    - Sub-agent orchestration logs (calls to Prompt/Program/Signal/Attribution AI)
    - Completion status for retry functionality
    """
    __tablename__ = "hyper_ai_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("hyper_ai_conversations.id"), nullable=False, index=True)

    # Message content
    role = Column(String(20), nullable=False)  # user / assistant / system / tool
    content = Column(Text, nullable=False)  # Message content (markdown supported)

    # AI reasoning and tool usage (for assistant messages)
    reasoning_snapshot = Column(Text, nullable=True)  # AI thinking process (chain-of-thought, extended thinking)
    tool_calls_log = Column(Text, nullable=True)  # JSON: [{name, arguments, result}, ...] - function calling log
    subagent_calls_log = Column(Text, nullable=True)  # JSON: [{agent, task, result}, ...] - sub-agent orchestration log

    # Completion status (for retry/continue functionality)
    is_complete = Column(Boolean, default=True)  # False = interrupted, can retry
    interrupt_reason = Column(Text, nullable=True)  # API error, timeout, user cancel, etc.

    # Token tracking (for compression calculation)
    token_count = Column(Integer, nullable=True)  # Estimated tokens in this message

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    # Relationships
    conversation = relationship("HyperAiConversation", back_populates="messages")


class BotConfig(Base):
    """Bot platform configuration (Telegram / Discord)"""
    __tablename__ = "bot_configs"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(20), unique=True, nullable=False)  # telegram / discord
    bot_token_encrypted = Column(Text, nullable=True)
    bot_username = Column(String(100), nullable=True)
    bot_app_id = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="disconnected")
    error_message = Column(Text, nullable=True)
    webhook_url = Column(Text, nullable=True)  # Last successful webhook URL (for auto-restore on restart)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class BotChatBinding(Base):
    """Track chat_ids that have interacted with the bot (for push broadcast)."""
    __tablename__ = "bot_chat_bindings"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(20), nullable=False)  # telegram / discord
    chat_id = Column(String(100), nullable=False)
    username = Column(String(100), nullable=True)
    display_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_message_at = Column(TIMESTAMP, server_default=func.current_timestamp())
