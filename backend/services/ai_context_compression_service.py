"""
AI Context Compression Service - Shared context management for all AI assistants

This module provides:
1. Token estimation for messages using tiktoken (including tool_calls)
2. Context window management with compression triggers
3. Conversation summarization using the user's configured LLM
4. Memory extraction during compression
5. Tool call history restoration from DB format to LLM API format

Architecture:
- restore_tool_calls_to_messages(): Converts DB [{tool, args, result}] back into
  standard LLM API messages (OpenAI tool_calls+tool or Anthropic tool_use+tool_result).
  Called by all 5 AI services when building cross-turn context.
- compress_messages(): Trigger compression at 70% of context window. Generates summary
  of older messages, extracts memories, replaces old messages with summary.
- find_compression_point(): Never splits inside a tool-call group boundary.

Usage:
    from services.ai_context_compression_service import (
        estimate_tokens,
        should_compress,
        compress_messages,
        restore_tool_calls_to_messages,
        calculate_token_usage,
    )

This module is split by responsibility into the `ai_context_compression_service/`
package (tokens, tool_restore, compression). The names below remain importable from
this path to preserve the public API.
"""
import os

__path__ = [os.path.join(os.path.dirname(__file__), "ai_context_compression_service")]

from services.ai_context_compression_service.tokens import (  # noqa: E402,F401
    COMPRESSION_THRESHOLD,
    MODEL_CONTEXT_WINDOWS,
    RESERVED_TOKENS,
    WARNING_RATIO,
    _estimate_single_message_tokens,
    _get_encoder,
    calculate_token_usage,
    estimate_messages_tokens,
    estimate_tokens,
    find_compression_point,
    get_context_window,
    should_compress,
)
from services.ai_context_compression_service.tool_restore import (  # noqa: E402,F401
    _restore_anthropic_tool_calls,
    _restore_openai_tool_calls,
    restore_tool_calls_to_messages,
)
from services.ai_context_compression_service.compression import (  # noqa: E402,F401
    COMPRESSION_PROMPT,
    CompressionResult,
    compress_messages,
    filter_messages_by_compression,
    generate_summary,
    get_last_compression_point,
    update_compression_points,
)
