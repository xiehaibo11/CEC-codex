"""Core API helpers for AI program generation."""
import json
import logging
import random
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

API_MAX_RETRIES = 5
API_BASE_DELAY = 1.0  # seconds
API_MAX_DELAY = 16.0  # seconds
RETRYABLE_STATUS_CODES = {502, 503, 504, 429}


def _should_retry_api(status_code: Optional[int], error: Optional[str]) -> bool:
    """Check if API error is retryable."""
    if status_code and status_code in RETRYABLE_STATUS_CODES:
        return True
    if error and any(x in error.lower() for x in ['timeout', 'connection', 'reset', 'eof']):
        return True
    return False


def _get_retry_delay(attempt: int) -> float:
    """Calculate retry delay with exponential backoff and jitter."""
    delay = min(API_BASE_DELAY * (2 ** attempt), API_MAX_DELAY)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter

def _call_anthropic_streaming(endpoint: str, payload: dict, headers: dict, timeout: int = 180) -> dict:
    """
    Call Anthropic API with streaming to avoid Cloudflare timeout.

    Streaming keeps the connection alive by sending data chunks continuously,
    preventing gateway timeouts (504) from Cloudflare or other proxies.

    Returns: dict with same structure as non-streaming response
        {"content": [...], "stop_reason": "..."}
    """
    # Enable streaming
    payload = payload.copy()
    payload["stream"] = True

    content_blocks = []  # Accumulated content blocks
    current_block = None  # Current block being built
    current_block_index = -1
    stop_reason = None

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout, stream=True)
    except requests.exceptions.Timeout as e:
        raise Exception(f"Timeout after {timeout}s: {str(e)}")
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Connection error: {str(e)}")
    except Exception as e:
        raise Exception(f"{type(e).__name__}: {str(e)}")

    if response.status_code != 200:
        # Return error info for caller to handle
        error_body = response.text[:1000] if response.text else "empty response"
        raise Exception(f"HTTP {response.status_code}: {error_body}")

    # Parse SSE stream - use explicit UTF-8 decoding to avoid encoding issues
    for line_bytes in response.iter_lines():
        if not line_bytes:
            continue
        # Decode with UTF-8 explicitly
        line = line_bytes.decode('utf-8')
        if line.startswith("event:"):
            continue  # Skip event type lines, we parse data directly
        if not line.startswith("data:"):
            continue

        data_str = line[5:].strip()  # Remove "data:" prefix
        if data_str == "[DONE]":
            break

        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        event_type = data.get("type", "")

        if event_type == "content_block_start":
            # New content block starting
            current_block_index = data.get("index", 0)
            block_data = data.get("content_block", {})
            block_type = block_data.get("type", "")

            if block_type == "text":
                current_block = {"type": "text", "text": ""}
            elif block_type == "thinking":
                current_block = {"type": "thinking", "thinking": ""}
            elif block_type == "tool_use":
                current_block = {
                    "type": "tool_use",
                    "id": block_data.get("id", ""),
                    "name": block_data.get("name", ""),
                    "input": ""  # Will accumulate JSON string, parse at end
                }

        elif event_type == "content_block_delta":
            # Incremental content
            delta = data.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta" and current_block:
                current_block["text"] += delta.get("text", "")
            elif delta_type == "thinking_delta" and current_block:
                current_block["thinking"] += delta.get("thinking", "")
            elif delta_type == "input_json_delta" and current_block:
                current_block["input"] += delta.get("partial_json", "")

        elif event_type == "content_block_stop":
            # Block complete, add to list
            if current_block:
                # Parse tool_use input from accumulated JSON string
                if current_block.get("type") == "tool_use":
                    input_str = current_block.get("input", "")
                    if input_str:
                        try:
                            current_block["input"] = json.loads(input_str)
                        except json.JSONDecodeError:
                            current_block["input"] = {}
                    else:
                        current_block["input"] = {}
                content_blocks.append(current_block)
                current_block = None

        elif event_type == "message_delta":
            # Message-level delta (contains stop_reason)
            delta = data.get("delta", {})
            stop_reason = delta.get("stop_reason")

    return {
        "content": content_blocks,
        "stop_reason": stop_reason
    }


# Anthropic format tools (pre-converted for efficiency)
