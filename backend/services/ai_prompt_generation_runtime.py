"""
Runtime setup helpers for AI prompt generation.
"""
import json
import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import Account, AiPromptConversation, AiPromptMessage
from services.ai_context_compression_service import (
    compress_messages,
    update_compression_points,
    restore_tool_calls_to_messages,
    get_last_compression_point,
    filter_messages_by_compression,
)
from services.ai_decision_service import (
    build_chat_completion_endpoints,
    build_llm_headers,
    detect_api_format,
)
from services.ai_prompt_generation_core import load_system_prompt
from services.ai_prompt_shared_tools import execute_get_prompt_context

logger = logging.getLogger(__name__)


def resolve_prompt_api_config(
    account: Optional[Account] = None,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Resolve LLM API config from explicit config or account."""
    if llm_config:
        return (
            {
                "base_url": llm_config.get("base_url"),
                "api_key": llm_config.get("api_key"),
                "model": llm_config.get("model"),
                "api_format": llm_config.get("api_format", "openai"),
            },
            "Hyper AI",
            None,
        )

    if account:
        return (
            {
                "base_url": account.base_url,
                "api_key": account.api_key,
                "model": account.model,
                "api_format": detect_api_format(account.base_url)[1] or "openai",
            },
            account.name,
            None,
        )

    return None, None, "No LLM configuration provided"


def build_system_prompt_with_context(
    db: Session,
    prompt_id: Optional[int],
    request_id: str,
) -> str:
    """Load the system prompt and append current prompt context when available."""
    system_prompt = load_system_prompt()

    if not prompt_id:
        return system_prompt

    context_info = execute_get_prompt_context(db, prompt_id)
    try:
        context_data = json.loads(context_info)
        if not context_data.get("success"):
            return system_prompt

        context_section = "\n\n## CURRENT CONTEXT\n"
        context_section += f"You are editing prompt ID: {prompt_id}\n"
        if context_data.get("prompt"):
            p = context_data["prompt"]
            context_section += f"- Prompt Name: {p.get('name', 'Unnamed')}\n"
            if p.get("content"):
                # Truncate if too long
                content = p["content"]
                if len(content) > 500:
                    content = content[:500] + "..."
                context_section += f"- Current Content:\n```\n{content}\n```\n"
        if context_data.get("bound_traders"):
            traders = context_data["bound_traders"]
            context_section += f"\nThis prompt is bound to {len(traders)} AI Trader(s):\n"
            for t in traders[:5]:  # Limit to 5
                context_section += f"- {t.get('name')} (ID: {t.get('id')}, Exchange: {t.get('exchange')})\n"
        else:
            context_section += "\nThis prompt is not bound to any AI Trader yet.\n"
        return system_prompt + context_section
    except Exception as e:
        logger.warning(f"[AI Prompt Gen {request_id}] Failed to inject context: {e}")
        return system_prompt


def get_or_create_conversation(
    db: Session,
    conversation_id: Optional[int],
    user_id: int,
    prompt_id: Optional[int],
    user_message: str,
    request_id: str,
) -> AiPromptConversation:
    """Load or create the prompt generation conversation."""
    conversation = None
    if conversation_id:
        conversation = db.query(AiPromptConversation).filter(
            AiPromptConversation.id == conversation_id,
            AiPromptConversation.user_id == user_id,
        ).first()

    if conversation:
        return conversation

    title = user_message[:50] + "..." if len(user_message) > 50 else user_message
    conversation = AiPromptConversation(
        user_id=user_id,
        prompt_id=prompt_id,
        title=title,
    )
    db.add(conversation)
    db.flush()
    logger.info(f"[AI Prompt Gen {request_id}] Created conversation: id={conversation.id}, prompt_id={prompt_id}")
    return conversation


def save_user_message(
    db: Session,
    conversation: AiPromptConversation,
    user_message: str,
) -> AiPromptMessage:
    """Persist the user message before preparing LLM history."""
    user_msg = AiPromptMessage(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    db.flush()
    return user_msg


def build_prompt_messages(
    db: Session,
    conversation: AiPromptConversation,
    user_msg: AiPromptMessage,
    system_prompt: str,
    user_message: str,
    api_config: Dict[str, Any],
) -> list:
    """Build LLM messages with compression support."""
    messages = [{"role": "system", "content": system_prompt}]

    # Check compression points - inject summary for compressed messages
    cp = get_last_compression_point(conversation)
    if cp and cp.get("summary"):
        messages.append({
            "role": "system",
            "content": f"[Previous conversation summary]\n{cp['summary']}",
        })

    # Load history, filter by compression point
    history = db.query(AiPromptMessage).filter(
        AiPromptMessage.conversation_id == conversation.id,
        AiPromptMessage.id != user_msg.id,
    ).order_by(AiPromptMessage.created_at).limit(100).all()

    history = filter_messages_by_compression(history, cp)

    last_message_id = history[-1].id if history else None

    # Restore tool_calls into proper LLM message format
    history_dicts = [
        {
            "role": m.role,
            "content": m.content,
            "tool_calls_log": m.tool_calls_log,
            "reasoning_snapshot": m.reasoning_snapshot,
        }
        for m in history
    ]
    restored = restore_tool_calls_to_messages(
        history_dicts,
        api_config.get("api_format", "openai"),
        model=api_config.get("model", ""),
    )
    messages.extend(restored)

    messages.append({"role": "user", "content": user_message})

    # Apply compression if needed (api_config already set above)
    result = compress_messages(messages, api_config, db=db)
    messages = result["messages"]

    # Update compression_points if compression occurred
    if result["compressed"] and result["summary"] and last_message_id:
        update_compression_points(
            conversation,
            last_message_id,
            result["summary"],
            result["compressed_at"],
            db,
        )

    return messages


def prepare_prompt_generation_context(
    db: Session,
    api_config: Dict[str, Any],
    user_id: int,
    prompt_id: Optional[int],
    conversation_id: Optional[int],
    user_message: str,
    request_id: str,
) -> Dict[str, Any]:
    """Prepare system prompt, conversation row, user message, and LLM messages."""
    system_prompt = build_system_prompt_with_context(db, prompt_id, request_id)
    conversation = get_or_create_conversation(
        db,
        conversation_id,
        user_id,
        prompt_id,
        user_message,
        request_id,
    )
    user_msg = save_user_message(db, conversation, user_message)
    messages = build_prompt_messages(
        db,
        conversation,
        user_msg,
        system_prompt,
        user_message,
        api_config,
    )
    return {
        "conversation": conversation,
        "messages": messages,
    }


def build_api_request_context(
    api_config: Dict[str, Any],
) -> Tuple[Optional[str], list, Optional[Dict[str, str]], Optional[str]]:
    """Resolve API format, endpoints, and headers."""
    endpoint, api_format = detect_api_format(api_config["base_url"])
    if not endpoint:
        return api_format, [], None, "Invalid API configuration"

    if api_format == "anthropic":
        endpoints = [endpoint]
    else:
        endpoints = build_chat_completion_endpoints(api_config["base_url"], api_config["model"])
        if not endpoints:
            return api_format, [], None, "Invalid API configuration"

    headers = build_llm_headers(api_format, api_config["api_key"], api_config["base_url"])
    return api_format, endpoints, headers, None
