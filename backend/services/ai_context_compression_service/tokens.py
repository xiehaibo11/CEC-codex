"""
Token estimation and context-window management for AI context compression.

Provides tiktoken-based token counting (including tool_calls), per-model context
window lookup, compression-trigger checks, usage-ratio calculation for the
frontend warning, and the tool-call-aware compression split point finder.
"""
import json
import logging
from typing import Any, Dict, List, Tuple

import tiktoken

logger = logging.getLogger(__name__)

# Initialize tiktoken encoder (cl100k_base works for GPT-4, Claude, and most models)
_encoder = None

def _get_encoder():
    """Lazy load tiktoken encoder."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


# Model context window sizes (updated 2026-03)
MODEL_CONTEXT_WINDOWS = {
    # OpenAI - GPT-5 series (must be listed before gpt-4 to match first)
    "gpt-5.4": 272000,
    "gpt-5.2": 400000,
    "gpt-5": 400000,
    # OpenAI - GPT-4 series
    "gpt-4.1": 1047576,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    # OpenAI - o-series reasoning models
    "o4-mini": 200000,
    "o3": 200000,
    "o3-mini": 200000,
    "o1": 200000,
    "o1-mini": 128000,
    # Anthropic
    "claude-opus-4": 200000,
    "claude-sonnet-4": 200000,
    "claude-haiku-4": 200000,
    "claude-3": 200000,
    "claude-sonnet": 200000,
    "claude-opus": 200000,
    "claude-haiku": 200000,
    # Google - Gemini 3 series (must be listed before gemini-2)
    "gemini-3": 1000000,
    "gemini-2.5": 1000000,
    "gemini-2": 1000000,
    "gemini-1.5": 1000000,
    # Deepseek V4 series (1M context)
    "deepseek-v4": 1000000,
    # Legacy aliases (mapped to V4 by API)
    "deepseek-chat": 1000000,
    "deepseek-reasoner": 1000000,
    # Qwen - 3.5 series (must be listed before qwen3)
    "qwen3.5": 262144,
    "qwen3-coder": 262144,
    "qwen3": 262144,
    "qwen-max": 262144,
    "qwen-plus": 131072,
    "qwen-turbo": 131072,
    # xAI Grok
    "grok-4.1": 2000000,
    "grok-4-fast": 2000000,
    "grok-4": 256000,
    "grok-3": 131072,
    # Meta Llama
    "llama-4-scout": 10000000,
    "llama-4-maverick": 1000000,
    "llama-4": 1000000,
    # Moonshot
    "moonshot-v1-128k": 128000,
    "moonshot-v1-32k": 32000,
    "moonshot-v1-8k": 8000,
    # GLM (Zhipu)
    "glm-5": 200000,
    "glm-4": 200000,
    # MiniMax
    "minimax-m2": 204800,
}

# Compression threshold (70% of context window - conservative for tokenizer differences)
COMPRESSION_THRESHOLD = 0.7

# Reserved tokens for system prompt and response
RESERVED_TOKENS = 4000


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text using tiktoken.
    Uses cl100k_base encoding which works for GPT-4, Claude, and most models.
    """
    if not text:
        return 0

    try:
        enc = _get_encoder()
        return len(enc.encode(text))
    except Exception as e:
        logger.warning(f"tiktoken encoding failed, using fallback: {e}")
        # Fallback: rough estimate of 4 chars per token
        return max(len(text) // 4, 1)


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    Estimate total tokens for a list of messages.

    Handles standard messages (role + content) as well as tool-call messages:
    - OpenAI format: "tool_calls" field on assistant messages (function name + arguments JSON)
    - Anthropic format: content list with tool_use/tool_result blocks
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            # Anthropic format: content is a list of blocks
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        total += estimate_tokens(item["text"])
                    elif item.get("type") == "tool_use":
                        # Count tool name + serialized input
                        total += estimate_tokens(item.get("name", ""))
                        total += estimate_tokens(json.dumps(item.get("input", {})))
                    elif item.get("type") == "tool_result":
                        tc = item.get("content", "")
                        total += estimate_tokens(tc) if isinstance(tc, str) else 20
        # OpenAI format: tool_calls field on assistant messages
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                total += estimate_tokens(fn.get("name", ""))
                total += estimate_tokens(fn.get("arguments", ""))
        # Add overhead for role and formatting
        total += 4
    return total


def get_context_window(model: str) -> int:
    """Get context window size for a model."""
    model_lower = model.lower()

    # Check exact matches first
    for key, size in MODEL_CONTEXT_WINDOWS.items():
        if key in model_lower:
            return size

    # Default fallback (128K is the minimum for modern models in 2026)
    logger.warning(f"Unknown model '{model}' for context window, using 128K fallback")
    return 128000


def should_compress(
    messages: List[Dict[str, Any]],
    model: str,
    threshold: float = COMPRESSION_THRESHOLD
) -> Tuple[bool, int, int]:
    """
    Check if conversation should be compressed.

    Returns:
        (should_compress, current_tokens, max_tokens)
    """
    context_window = get_context_window(model)
    max_tokens = int(context_window * threshold) - RESERVED_TOKENS
    current_tokens = estimate_messages_tokens(messages)

    return (current_tokens > max_tokens, current_tokens, max_tokens)


# Show warning when usage reaches 85% of compression threshold (15% remaining)
WARNING_RATIO = 0.85


def calculate_token_usage(
    messages: List[Dict[str, Any]],
    model: str
) -> Dict[str, Any]:
    """
    Calculate token usage ratio for a conversation.
    Used to display context usage warning in frontend.

    usage_ratio is relative to max_tokens (the compression trigger line):
    - 0.85 = 85% used, 15% remaining -> show_warning starts
    - 1.0  = at compression line, 0% remaining
    - >1.0 = over limit, capped to 1.0 for display

    Returns:
        {
            "current_tokens": int,
            "max_tokens": int,
            "usage_ratio": float (0.0-1.0, capped),
            "show_warning": bool (True when >= 85% of compression line)
        }
    """
    context_window = get_context_window(model)
    max_tokens = int(context_window * COMPRESSION_THRESHOLD) - RESERVED_TOKENS
    current_tokens = estimate_messages_tokens(messages)
    raw_ratio = current_tokens / max_tokens if max_tokens > 0 else 0

    return {
        "current_tokens": current_tokens,
        "max_tokens": max_tokens,
        "usage_ratio": round(min(raw_ratio, 1.0), 3),
        "show_warning": raw_ratio >= WARNING_RATIO
    }


def find_compression_point(
    messages: List[Dict[str, Any]],
    target_tokens: int
) -> int:
    """
    Find the index where to split messages for compression.
    Keep recent messages, compress older ones.

    IMPORTANT: Never splits inside a tool-call group. A tool-call group is:
    - OpenAI:    assistant(tool_calls) + tool(result)... + assistant(final)
    - Anthropic: assistant(tool_use) + user(tool_result) + assistant(final)
    The split point is adjusted outward to the nearest group boundary.

    Returns index of first message to keep (messages before this will be compressed).
    """
    if not messages:
        return 0

    # Build a map of tool-call group boundaries.
    # Each group starts at an assistant message with tool_calls and ends at the
    # next assistant message that has NO tool_calls (the final reply).
    group_start_of = {}  # index -> group start index
    current_group_start = None
    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        has_tool_calls = bool(msg.get("tool_calls"))
        # Anthropic: assistant content list with tool_use blocks
        if not has_tool_calls and isinstance(msg.get("content"), list):
            has_tool_calls = any(
                b.get("type") == "tool_use" for b in msg["content"] if isinstance(b, dict)
            )
        if role == "assistant" and has_tool_calls:
            current_group_start = i
        if current_group_start is not None:
            group_start_of[i] = current_group_start
        # End group when we hit an assistant message without tool_calls
        if role == "assistant" and not has_tool_calls and current_group_start is not None:
            current_group_start = None

    # Calculate tokens from the end to find raw split point
    tokens_from_end = 0
    keep_from_index = len(messages)

    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        msg_tokens = _estimate_single_message_tokens(msg)
        if tokens_from_end + msg_tokens > target_tokens:
            break
        tokens_from_end += msg_tokens
        keep_from_index = i

    # Adjust: if split lands inside a tool-call group, move to group start
    if keep_from_index in group_start_of:
        keep_from_index = group_start_of[keep_from_index]

    # Keep at least the last 2 messages
    return min(keep_from_index, len(messages) - 2)


def _estimate_single_message_tokens(msg: Dict[str, Any]) -> int:
    """Estimate tokens for a single message (content + tool_calls)."""
    tokens = 0
    content = msg.get("content", "")
    if isinstance(content, str):
        tokens += estimate_tokens(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    tokens += estimate_tokens(item["text"])
                elif item.get("type") in ("tool_use", "tool_result"):
                    tokens += estimate_tokens(json.dumps(item))
    for tc in msg.get("tool_calls", []):
        fn = tc.get("function", {})
        tokens += estimate_tokens(fn.get("name", ""))
        tokens += estimate_tokens(fn.get("arguments", ""))
    tokens += 4  # overhead
    return tokens
