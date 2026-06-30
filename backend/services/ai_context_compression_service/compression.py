"""
Conversation summarization and compression for AI context management.

Generates structured summaries of older messages via the configured LLM, triggers
compression at the threshold (replacing old messages with a summary + extracting
memories in the background), and manages per-conversation compression points used to
filter ORM messages on subsequent turns.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

import requests
from sqlalchemy.orm import Session

from services.ai_stream_service import submit_ai_background_task
from services.system_logger import system_logger
from services.ai_context_compression_service.tokens import (
    estimate_messages_tokens,
    estimate_tokens,
    find_compression_point,
    should_compress,
)

logger = logging.getLogger(__name__)


class CompressionResult(TypedDict):
    """Result of compression operation."""
    messages: List[Dict[str, Any]]  # Compressed message list
    compressed: bool  # Whether compression was performed
    summary: Optional[str]  # Summary text if compressed
    compressed_message_count: int  # Number of messages compressed
    compressed_at: Optional[str]  # ISO timestamp of compression


COMPRESSION_PROMPT = """You are a conversation context compressor for a crypto trading AI assistant.
Create a structured summary that preserves all critical context needed to continue the conversation seamlessly.

## What to preserve (in order of priority):

1. **Current task state**: What is the user working on? What stage? (e.g. "Building intraday BTC strategy, v2 generated with EMA crossover + RSI filter, not yet saved")

2. **Key decisions and parameters**: Specific numbers, thresholds, configurations confirmed (e.g. "5x leverage, 2% TP, 1% SL, EMA 9/21")

3. **Tool call results**: Key findings from tools - positions, balances, market data, diagnostics. Summarize findings, not raw data.

4. **Code/strategy change log**: Do NOT include full code. Instead record:
   - What was changed and why (e.g. "Relaxed depth_ratio filter from 0.001 to 0.01 because original was too strict")
   - Version progression (e.g. "v1→v2: added volume confirmation; v2→v3: removed OI filter")
   - Whether the latest version was saved by user or still unsaved

5. **Test results and issues found**: Backtest/live test outcomes, bugs discovered, performance problems, unexpected behavior (e.g. "24h backtest: 0 trades executed due to strict depth filter")

6. **Disagreements and open questions**: Points where user disagreed with AI suggestion, alternative approaches discussed but not chosen, unresolved debates

7. **Pending items**: Unresolved requests, next steps discussed, things user asked to do later

8. **User preferences**: Trading style, risk tolerance, workflow preferences mentioned

## Rules:
- Be specific: include actual numbers, coin names, parameter values
- Be thorough: target 4000-6500 words (this is intentional — modern LLMs have large context windows, preserve detail over brevity)
- Use structured format with clear section headers
- Write as context briefing for the AI's next turn, not as a chat log
- Do NOT include greetings or meta-discussion about the conversation itself
- For code changes: describe the logic change, NOT the code itself

Conversation to summarize:
{conversation}

Structured summary:"""


def generate_summary(
    messages_to_compress: List[Dict[str, Any]],
    api_config: Dict[str, Any]
) -> Optional[str]:
    """
    Generate a summary of messages using LLM.

    Args:
        messages_to_compress: Messages to summarize
        api_config: LLM configuration with base_url, api_key, model

    Returns:
        Summary text or None if failed
    """
    if not messages_to_compress:
        return None

    # Build conversation text (handles both plain messages and tool-call messages)
    conv_parts = []
    for msg in messages_to_compress:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            conv_parts.append(f"{role.upper()}: {content}")
        elif isinstance(content, list):
            # Anthropic format or tool_use/tool_result blocks
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        conv_parts.append(f"ASSISTANT: [Called tool: {block.get('name', '?')}]")
                    elif block.get("type") == "tool_result":
                        tc = block.get("content", "")
                        snippet = tc[:200] if isinstance(tc, str) else str(tc)[:200]
                        conv_parts.append(f"TOOL_RESULT: {snippet}")
        # OpenAI tool_calls on assistant messages
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
            conv_parts.append(f"ASSISTANT: [Called tools: {', '.join(names)}]")

    conversation_text = "\n\n".join(conv_parts)

    # Prepare API call
    base_url = api_config.get("base_url", "")
    api_key = api_config.get("api_key", "")
    model = api_config.get("model", "")
    api_format = api_config.get("api_format", "openai")

    if not all([base_url, api_key, model]):
        logger.warning("Incomplete API config for compression")
        return None

    prompt = COMPRESSION_PROMPT.format(conversation=conversation_text[:30000])

    try:
        from services.ai_decision_service import build_chat_completion_endpoints, build_llm_payload, build_llm_headers

        if api_format == "anthropic":
            endpoints = build_chat_completion_endpoints(base_url, model)
            endpoint = endpoints[0] if endpoints else f"{base_url.rstrip('/')}/messages"
        else:
            endpoints = build_chat_completion_endpoints(base_url, model)
            endpoint = endpoints[0] if endpoints else f"{base_url}/chat/completions"

        # Use unified headers/payload builders (see build_llm_payload in ai_decision_service)
        headers = build_llm_headers(api_format, api_key, base_url)
        body = build_llm_payload(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            api_format=api_format,
            max_tokens=12000,
        )

        response = requests.post(endpoint, headers=headers, json=body, timeout=600)

        if response.status_code != 200:
            resp_snippet = response.text[:500] if response.text else "empty"
            logger.error(
                f"Compression API error: status={response.status_code}, "
                f"model={model}, endpoint={endpoint}, "
                f"prompt_tokens~{estimate_tokens(prompt)}, "
                f"response={resp_snippet}"
            )
            system_logger.add_log(
                "ERROR", "system_error",
                f"Compression API error: {response.status_code}",
                {
                    "model": model,
                    "endpoint": endpoint,
                    "status": response.status_code,
                    "prompt_tokens": estimate_tokens(prompt),
                    "response_snippet": resp_snippet[:200],
                }
            )
            return None

        data = response.json()

        # Extract content based on format
        if api_format == "anthropic":
            content = data.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
        else:
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")

    except Exception as e:
        logger.error(f"Compression failed: {type(e).__name__}: {e}")
        system_logger.add_log(
            "ERROR", "system_error",
            f"Compression exception: {type(e).__name__}",
            {"model": model, "error": str(e)[:300]}
        )

    return None


def compress_messages(
    messages: List[Dict[str, Any]],
    api_config: Dict[str, Any],
    keep_system: bool = True,
    db: Optional[Session] = None,
    extract_memories: bool = True
) -> CompressionResult:
    """
    Compress conversation messages if needed.

    Args:
        messages: Full message list including system prompt
        api_config: LLM configuration
        keep_system: Whether to preserve system messages
        db: Database session (required for memory extraction)
        extract_memories: Whether to extract memories during compression

    Returns:
        CompressionResult with compressed messages and metadata
    """
    model = api_config.get("model", "")
    needs_compression, current, max_tokens = should_compress(messages, model)

    if not needs_compression:
        return CompressionResult(
            messages=messages,
            compressed=False,
            summary=None,
            compressed_message_count=0,
            compressed_at=None
        )

    logger.info(f"Compressing conversation: {current} tokens > {max_tokens} limit")

    # Separate system messages and conversation
    system_messages = []
    conversation_messages = []

    for msg in messages:
        if msg.get("role") == "system" and keep_system:
            system_messages.append(msg)
        else:
            conversation_messages.append(msg)

    # Find compression point (keep ~40% of max tokens for recent messages)
    target_keep = int(max_tokens * 0.4)
    split_index = find_compression_point(conversation_messages, target_keep)

    if split_index <= 0:
        # Nothing to compress
        return CompressionResult(
            messages=messages,
            compressed=False,
            summary=None,
            compressed_message_count=0,
            compressed_at=None
        )

    # Split messages
    to_compress = conversation_messages[:split_index]
    to_keep = conversation_messages[split_index:]

    # Extract memories in background thread (non-blocking)
    if extract_memories and db:
        try:
            mem_parts = []
            for m in to_compress:
                role = m.get('role', 'unknown').upper()
                content = m.get('content', '')
                if isinstance(content, str) and content.strip():
                    mem_parts.append(f"{role}: {content}")
                for tc in m.get('tool_calls', []):
                    fn = tc.get('function', {})
                    mem_parts.append(f"TOOL_CALL: {fn.get('name', '?')}")
            conv_text = "\n\n".join(mem_parts)

            # Copy api_config to avoid thread-safety issues
            api_config_copy = dict(api_config)

            def _extract_memories_bg(conv_text_bg, api_cfg_bg):
                """Background thread for memory extraction + batch dedup."""
                from database.connection import SessionLocal
                bg_db = SessionLocal()
                try:
                    from services.hyper_ai_memory_service import process_compression_memories
                    count = process_compression_memories(bg_db, conv_text_bg, api_cfg_bg)
                    logger.warning(f"[Compression] Background memory extraction done: {count} memories")
                except Exception as e:
                    logger.warning(f"[Compression] Background memory extraction failed: {type(e).__name__}: {e}")
                finally:
                    bg_db.close()

            submit_ai_background_task(_extract_memories_bg, conv_text, api_config_copy)
        except Exception as e:
            logger.warning(f"[Compression] Failed to start memory extraction thread: {e}")

    # Generate summary
    summary = generate_summary(to_compress, api_config)

    if not summary:
        # Fallback: just truncate without summary
        logger.warning("Summary generation failed, truncating without summary")
        return CompressionResult(
            messages=system_messages + to_keep,
            compressed=True,
            summary=None,
            compressed_message_count=len(to_compress),
            compressed_at=datetime.now(timezone.utc).isoformat()
        )

    # Build compressed message list
    compressed = system_messages.copy()

    # Add summary as a system message
    compressed.append({
        "role": "system",
        "content": f"[Previous conversation summary]\n{summary}"
    })

    # Add recent messages
    compressed.extend(to_keep)

    new_tokens = estimate_messages_tokens(compressed)
    logger.info(f"Compression complete: {current} -> {new_tokens} tokens")

    return CompressionResult(
        messages=compressed,
        compressed=True,
        summary=summary,
        compressed_message_count=len(to_compress),
        compressed_at=datetime.now(timezone.utc).isoformat()
    )


def update_compression_points(
    conversation: Any,
    last_message_id: int,
    summary: str,
    compressed_at: str,
    db: Session
) -> None:
    """
    Update conversation's compression_points field after compression.

    Args:
        conversation: Conversation ORM object (any type)
        last_message_id: ID of the last message before compression point
        summary: Summary text of compressed messages
        compressed_at: ISO timestamp of compression
        db: Database session
    """
    # Parse existing compression points
    existing = []
    if conversation.compression_points:
        try:
            existing = json.loads(conversation.compression_points)
        except (json.JSONDecodeError, TypeError):
            existing = []

    # Add new compression point
    new_point = {
        "message_id": last_message_id,
        "summary": summary,
        "compressed_at": compressed_at
    }
    existing.append(new_point)

    # Update conversation
    conversation.compression_points = json.dumps(existing)
    db.commit()
    logger.info(f"Updated compression_points for conversation {conversation.id}")


def get_last_compression_point(conversation: Any) -> Optional[Dict[str, Any]]:
    """
    Get the most recent compression point from a conversation.

    Returns:
        {"message_id": int, "summary": str, "compressed_at": str} or None
    """
    if not conversation.compression_points:
        return None
    try:
        points = json.loads(conversation.compression_points)
        if isinstance(points, list) and points:
            return points[-1]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def filter_messages_by_compression(
    messages_orm: list,
    compression_point: Optional[Dict[str, Any]]
) -> list:
    """
    Filter ORM message objects by compression point.
    Only keep messages with id > compression_point["message_id"].

    Args:
        messages_orm: List of ORM message objects (must have .id attribute)
        compression_point: Result from get_last_compression_point()

    Returns:
        Filtered list of ORM message objects (after compression point)
    """
    if not compression_point:
        return messages_orm

    cp_message_id = compression_point.get("message_id", 0)
    return [m for m in messages_orm if m.id > cp_message_id]
