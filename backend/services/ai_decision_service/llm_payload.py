"""LLM request payload, headers, and response parsing helpers.

Builds unified chat-completion payloads/headers, converts between OpenAI and
Anthropic message/tool formats, and extracts reasoning / text from responses.
"""
import json
import re
from typing import Any, Dict, List, Optional

from services.ai_decision_service.llm_models import (
    get_max_tokens,
    is_minimax_anthropic_url,
    is_new_openai_model,
    is_reasoning_model,
    requires_deepseek_reasoning_content,
)


def build_llm_headers(api_format: str, api_key: str, base_url: Optional[str] = None) -> dict:
    """Build HTTP headers for LLM API calls.

    Args:
        api_format: 'anthropic' or 'openai'
        api_key: The API key
        base_url: Optional URL used for provider-specific auth quirks
    """
    headers = {"Content-Type": "application/json"}
    if api_format == "anthropic":
        if is_minimax_anthropic_url(base_url):
            # MiniMax's Anthropic-compatible /anthropic gateway uses the
            # Messages schema but rejects Anthropic's official x-api-key header.
            # Keep this scoped to MiniMax URLs so the official Anthropic API is unchanged.
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def convert_tools_to_anthropic(openai_tools: List[Dict]) -> List[Dict]:
    """Convert OpenAI format tools to Anthropic format."""
    anthropic_tools = []
    for tool in openai_tools:
        if tool.get("type") == "function":
            func = tool["function"]
            anthropic_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}})
            })
    return anthropic_tools


def convert_messages_to_anthropic(openai_messages: List[Dict]) -> tuple:
    """Convert OpenAI format messages to Anthropic format.

    Returns: (system_prompt, anthropic_messages)
    Anthropic requires system prompt to be separate from messages.
    Also, multiple consecutive tool results must be merged into one user message.
    """
    system_prompt = ""
    anthropic_messages = []
    pending_tool_results = []

    def flush_tool_results():
        nonlocal pending_tool_results
        if pending_tool_results:
            anthropic_messages.append({
                "role": "user",
                "content": pending_tool_results
            })
            pending_tool_results = []

    def clean_tool_use_blocks(blocks):
        """Fix input field format (some proxies return '' instead of {})."""
        if not isinstance(blocks, list):
            return blocks
        cleaned = []
        for block in blocks:
            if isinstance(block, dict):
                block_copy = block.copy()
                if block_copy.get("type") == "tool_use" and block_copy.get("input") == "":
                    block_copy["input"] = {}
                cleaned.append(block_copy)
            else:
                cleaned.append(block)
        return cleaned

    for msg in openai_messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            system_prompt = content
        elif role == "user":
            flush_tool_results()
            anthropic_messages.append({"role": "user", "content": content})
        elif role == "assistant":
            flush_tool_results()
            if "tool_use_blocks" in msg:
                cleaned_blocks = clean_tool_use_blocks(msg["tool_use_blocks"])
                anthropic_messages.append({
                    "role": "assistant",
                    "content": cleaned_blocks
                })
            else:
                anthropic_messages.append({"role": "assistant", "content": content})
        elif role == "tool":
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": content
            })

    flush_tool_results()
    return system_prompt, anthropic_messages


def extract_reasoning(message: dict) -> str:
    """Extract reasoning/thinking content from LLM API response message.

    Unified extraction for all providers. Currently supports:
    - DeepSeek V4/R1/Reasoner, Qwen QwQ, Grok-3-mini: 'reasoning_content' field
    - Some Qwen models: 'thinking' field

    Note: OpenAI o1/o3/o4 does not expose reasoning via API.
    Note: Claude extended thinking requires enabling in request (not yet supported).

    Args:
        message: The 'message' dict from LLM response (choices[0].message)

    Returns:
        Reasoning text or empty string if none found
    """
    # Strategy 1: reasoning_content (DeepSeek V4/R1, Qwen QwQ, Grok-3-mini)
    rc = message.get("reasoning_content")
    if rc and isinstance(rc, str) and rc.strip():
        return rc
    # Strategy 2: thinking field (some Qwen models via vLLM)
    tk = message.get("thinking")
    if tk and isinstance(tk, str) and tk.strip():
        return tk
    # Strategy 3: Claude thinking blocks in content array
    # {"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]}
    try:
        content_array = message.get("content")
        if isinstance(content_array, list):
            parts = []
            for block in content_array:
                if isinstance(block, dict) and block.get("type") == "thinking":
                    t = block.get("thinking")
                    if t and isinstance(t, str) and t.strip():
                        parts.append(t.strip())
            if parts:
                return "\n\n".join(parts)
    except Exception:
        pass
    # Strategy 4: Gemini thought parts
    # {"parts": [{"text": "...", "thought": true}, {"text": "..."}]}
    try:
        parts_array = message.get("parts")
        if isinstance(parts_array, list):
            parts = []
            for part in parts_array:
                if isinstance(part, dict) and part.get("thought"):
                    t = part.get("text")
                    if t and isinstance(t, str) and t.strip():
                        parts.append(t.strip())
            if parts:
                return "\n\n".join(parts)
    except Exception:
        pass
    # Strategy 5: MiniMax reasoning_details
    rd = message.get("reasoning_details")
    if isinstance(rd, list):
        parts = []
        for item in rd:
            if isinstance(item, dict):
                t = item.get("text")
                if t and isinstance(t, str) and t.strip():
                    parts.append(t.strip())
        if parts:
            return "\n\n".join(parts)
    return ""


# Regex to match <thinking>...</thinking> and <think>...</think> tags.
_THINKING_TAG_RE = re.compile(
    r'<think(?:ing)?>\s*([\s\S]*?)\s*</think(?:ing)?>',
    re.IGNORECASE
)


def strip_thinking_tags(content: str) -> tuple:
    """Strip <thinking>...</thinking> text tags from content.

    Some OpenAI-compatible proxies embed Claude's extended thinking as
    <thinking> text tags inside the content field. This extracts the
    thinking text and returns clean content.

    Returns:
        (clean_content, extracted_thinking) tuple.
        extracted_thinking is empty string if no tags found.
    """
    content_lower = (content or "").lower()
    if not content or ('<thinking>' not in content_lower and '<think>' not in content_lower):
        return (content, "")

    parts = []
    for m in _THINKING_TAG_RE.finditer(content):
        parts.append(m.group(1).strip())

    clean = _THINKING_TAG_RE.sub('', content).strip()
    return (clean, "\n\n".join(parts))


def build_llm_payload(
    model: str,
    messages: list,
    api_format: str,
    max_tokens: int = None,
    temperature: float = 0.7,
    tools: list = None,
    tool_choice: str = None,
    stream: bool = False,
) -> dict:
    """Build a correct LLM API payload with proper parameter handling.

    Automatically handles:
    - Reasoning models: omits temperature, uses max_completion_tokens (OpenAI)
    - Anthropic format: separates system messages, always uses max_tokens
    - GPT-5: adds reasoning_effort parameter
    - New OpenAI models (gpt-4o, o1, o3, etc.): max_completion_tokens

    Args:
        model: Model name (e.g. "gpt-4o", "o1", "claude-3-5-sonnet")
        messages: Chat messages list
        api_format: 'anthropic' or 'openai'
        max_tokens: Max output tokens (None = auto via get_max_tokens)
        temperature: Temperature value (ignored for reasoning models)
        tools: Tool definitions (format must match api_format)
        tool_choice: Tool choice strategy (e.g. "auto")
        stream: Whether to enable streaming
    """
    if max_tokens is None:
        max_tokens = get_max_tokens(model)

    reasoning = is_reasoning_model(model)
    new_model = is_new_openai_model(model)

    if api_format == "anthropic":
        # Anthropic: separate system messages, always use max_tokens
        system_parts = []
        api_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg["content"])
            else:
                api_messages.append(msg)

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)

        # Claude extended thinking: all Anthropic models support thinking
        # Returns thinking blocks in content array, billed as output tokens
        budget = min(4096, max_tokens - 1)
        if budget >= 1024:
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
    else:
        # OpenAI format
        payload = {
            "model": model,
            "messages": messages,
        }
        # Reasoning models don't support temperature
        if not reasoning and temperature is not None:
            payload["temperature"] = temperature

        # New models use max_completion_tokens, older use max_tokens
        if new_model:
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens

        # GPT-5 family: set reasoning_effort
        if "gpt-5" in (model or "").lower():
            payload["reasoning_effort"] = "low"

        # Gemini thinking: include thoughts in response for reasoning-class models
        # Works via OpenAI-compatible API with google.thinking_config extension
        model_lower = (model or "").lower()
        if reasoning and ("gemini" in model_lower):
            payload["google"] = {
                "thinking_config": {
                    "include_thoughts": True
                }
            }

    # Optional: tools
    if tools:
        payload["tools"] = tools
        if tool_choice and api_format != "anthropic":
            payload["tool_choice"] = tool_choice

    # Optional: streaming
    if stream:
        payload["stream"] = True

    # DeepSeek V4 thinking mode requires prior assistant messages to carry the
    # reasoning_content field when sent back in multi-turn history.
    if api_format != "anthropic":
        if requires_deepseek_reasoning_content(model):
            for msg in payload.get("messages", []):
                if msg.get("role") == "assistant" and "reasoning_content" not in msg:
                    msg["reasoning_content"] = ""

    return payload


def _extract_text_from_message(content: Any) -> str:
    """Normalize OpenAI/Anthropic style message content into a plain string."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                # Anthropic style: {"type": "text", "text": "..."}
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue

                # Some providers use {"type": "output_text", "content": "..."}
                content_value = item.get("content")
                if isinstance(content_value, str):
                    parts.append(content_value)
                    continue

                # Recursively handle nested content arrays
                nested = item.get("content")
                nested_text = _extract_text_from_message(nested)
                if nested_text:
                    parts.append(nested_text)
        return "\n".join(parts)

    if isinstance(content, dict):
        # Direct text fields
        for key in ("text", "content", "value"):
            value = content.get(key)
            if isinstance(value, str):
                return value

        # Nested structures
        for key in ("text", "content", "parts"):
            nested = content.get(key)
            nested_text = _extract_text_from_message(nested)
            if nested_text:
                return nested_text

    return ""
