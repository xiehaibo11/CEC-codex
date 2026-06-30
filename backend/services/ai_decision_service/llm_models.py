"""LLM model capability detection and API-format helpers.

Token sizing, API-format/endpoint detection, and reasoning/new-model markers.
"""
from typing import List, Optional


def get_max_tokens(model: str) -> int:
    """
    Get recommended max_tokens value based on model name.

    Different models have different max output token limits:
    - GPT-4-turbo: 4096 (needs special handling)
    - GPT-4o/4o-mini: 16384 (use 8000 for cost balance)
    - o1/o1-mini: 65536-100000 (use 12000-16000)
    - Claude: 64000 (use 12000 for cost balance)
    - Deepseek V4 Flash: 16000
    - Deepseek V4 Pro: 32000
    - Qwen: 8000-65536 (use 8000-16000)

    Args:
        model: Model name (e.g., "gpt-4-turbo", "claude-3-5-sonnet-20241022")

    Returns:
        Recommended max_tokens value (fallback: 4000 for unknown models)
    """
    model_lower = model.lower()

    # Special case: GPT-4-turbo has max output limit of 4096
    if 'gpt-4-turbo' in model_lower:
        return 4000

    # GPT-4.1 (ultra-large context model)
    if 'gpt-4.1' in model_lower:
        return 16000

    # DeepSeek V4 series (max output 384K, use 32000 for cost balance)
    if 'deepseek-v4-pro' in model_lower:
        return 32000
    if 'deepseek-v4-flash' in model_lower:
        return 16000

    # Legacy DeepSeek reasoning models (mapped to v4-flash by API)
    if 'deepseek-reasoner' in model_lower:
        return 16000

    # o1 series (note order: check o1-mini first, then o1)
    if 'o1-mini' in model_lower:
        return 12000
    if 'o1' in model_lower:
        return 16000

    # GPT-4o series
    if 'gpt-4o' in model_lower:
        return 8000

    # Claude series
    if 'claude' in model_lower:
        return 12000

    # Qwen series (note order: check qwen3 first, then qwen)
    if 'qwen3' in model_lower:
        return 16000
    if 'qwen' in model_lower:
        return 8000

    # GLM series (Z.ai models like GLM-4.7)
    if 'glm' in model_lower:
        return 16000

    # MiniMax M2 series
    if 'minimax' in model_lower:
        return 16000

    # Deepseek V4 series
    if 'deepseek-v4' in model_lower:
        return 16000

    # Legacy Deepseek-chat (mapped to v4-flash by API)
    if 'deepseek' in model_lower:
        return 16000

    # Fallback for unknown models (conservative safe value)
    return 4000
def detect_api_format(base_url: str) -> tuple:
    """Detect API format from URL and return (endpoint, format_type).

    Returns:
        tuple: (endpoint_url, format_type) where format_type is 'openai' or 'anthropic'
    """
    if not base_url:
        return (None, None)

    normalized = base_url.strip().rstrip('/')
    if not normalized:
        return (None, None)

    base_lower = normalized.lower()

    # Check if URL already ends with a complete endpoint
    if base_lower.endswith('/messages'):
        # Anthropic native format
        return (normalized, 'anthropic')
    elif base_lower.endswith('/chat/completions'):
        # OpenAI format, already complete
        return (normalized, 'openai')
    elif base_lower.endswith('/anthropic'):
        # Third-party Anthropic-compatible base URL, e.g. MiniMax.
        # Anthropic SDKs append /v1/messages internally; we use requests directly.
        return (f"{normalized}/v1/messages", 'anthropic')
    else:
        # No specific endpoint, append /chat/completions (default OpenAI format)
        return (f"{normalized}/chat/completions", 'openai')


def build_chat_completion_endpoints(base_url: str, model: Optional[str] = None) -> List[str]:
    """Build a list of possible chat completion endpoints for an OpenAI-compatible API.

    Supports Deepseek-specific behavior where both `/chat/completions` and `/v1/chat/completions`
    might be valid, depending on how the base URL is configured.
    Returns:
        List of endpoint URLs to try.
    """
    if not base_url:
        return []

    normalized = base_url.strip().rstrip('/')
    if not normalized:
        return []

    base_lower = normalized.lower()

    # Check if URL already ends with a complete endpoint
    if base_lower.endswith('/messages'):
        # Anthropic native format - use as-is
        return [normalized]
    elif base_lower.endswith('/chat/completions'):
        # OpenAI format, already complete - use as-is
        return [normalized]
    elif base_lower.endswith('/anthropic'):
        # Third-party Anthropic-compatible base URL, e.g. MiniMax.
        # Anthropic SDKs append /v1/messages internally; we use requests directly.
        return [f"{normalized}/v1/messages"]

    # No specific endpoint, build OpenAI-compatible endpoints
    endpoints: List[str] = []
    endpoints.append(f"{normalized}/chat/completions")

    is_deepseek = "deepseek.com" in base_lower

    if is_deepseek:
        # Deepseek supports both /chat/completions and /v1/chat/completions
        if base_lower.endswith('/v1'):
            without_v1 = normalized[:-3]
            endpoints.append(f"{without_v1}/chat/completions")
        else:
            endpoints.append(f"{normalized}/v1/chat/completions")

    # Use dict to preserve order while removing duplicates
    deduped = list(dict.fromkeys(endpoints))
    return deduped


# ---------------------------------------------------------------------------
# Unified LLM payload & headers builders
# ---------------------------------------------------------------------------
# ALL AI features (Trader, Prompt Gen, Program Gen, Signal Gen, Hyper AI,
# K-line Analysis, Attribution, Context Compression, Memory) MUST use these
# two functions to build API payloads and headers.
# When adding a NEW AI feature, import and call these instead of manually
# assembling payload dicts — this ensures correct parameter handling for
# reasoning models, new OpenAI models, Anthropic format, etc.
# ---------------------------------------------------------------------------

# DeepSeek models/aliases that currently use the V4 thinking-mode contract.
DEEPSEEK_REASONING_CONTENT_MODEL_MARKERS = [
    "deepseek-v4",
    "deepseek-reasoner",
    "deepseek-chat",
    "deepseek-r1",
]

# Canonical list of reasoning models that do NOT support temperature
# and require max_completion_tokens (OpenAI format only).
REASONING_MODEL_MARKERS = [
    # OpenAI
    "gpt-5", "o1-preview", "o1-mini", "o1-", "o1", "o3-", "o3", "o4-", "o4",
    # DeepSeek V4 and legacy aliases mapped to V4 behavior
    *DEEPSEEK_REASONING_CONTENT_MODEL_MARKERS,
    # Qwen
    "qwq", "qwen-plus-thinking", "qwen-max-thinking", "qwen3-thinking", "qwen-turbo-thinking",
    # Claude (extended thinking)
    "claude-4", "claude-sonnet-4-5",
    # Gemini (thinking mode)
    "gemini-2.5", "gemini-3", "gemini-2.0-flash-thinking",
    # Grok
    "grok-3-mini",
]

# Models that use max_completion_tokens instead of max_tokens (OpenAI format).
# This includes all reasoning models plus newer non-reasoning models.
NEW_MODEL_MARKERS = ["gpt-4o"]


def is_reasoning_model(model: str) -> bool:
    """Check if a model is a reasoning model (no temperature, special params)."""
    model_lower = (model or "").lower()
    return any(marker in model_lower for marker in REASONING_MODEL_MARKERS)


def requires_deepseek_reasoning_content(model: str) -> bool:
    """DeepSeek V4 thinking-mode models require reasoning_content on tool-call messages."""
    model_lower = (model or "").lower()
    return any(marker in model_lower for marker in DEEPSEEK_REASONING_CONTENT_MODEL_MARKERS)


def is_new_openai_model(model: str) -> bool:
    """Check if a model uses max_completion_tokens instead of max_tokens."""
    return is_reasoning_model(model) or any(
        marker in (model or "").lower() for marker in NEW_MODEL_MARKERS
    )


def is_minimax_anthropic_url(url: Optional[str]) -> bool:
    """Return True for MiniMax's Anthropic-compatible gateway URLs."""
    normalized = (url or "").strip().rstrip("/").lower()
    return (
        "api.minimax.io/anthropic" in normalized
        or "api.minimaxi.com/anthropic" in normalized
    )
