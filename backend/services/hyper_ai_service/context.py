"""Message and context assembly for Hyper AI chat requests.

Builds the LLM message list (system prompt + skill metadata, profile context,
long-term memory, compressed history, current user message) and the profile /
memory context blocks injected into the system prompt.
"""
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import (
    HyperAiProfile,
    HyperAiConversation,
    HyperAiMessage,
)
from services.hyper_ai_tools import HYPER_AI_TOOLS

from services.hyper_ai_service.llm_config import get_or_create_profile
from services.hyper_ai_service.prompts import load_system_prompt


def build_messages_for_api(
    db: Session,
    conversation_id: int,
    user_message: str,
    api_config: Dict[str, Any],
    include_tools: bool = True
) -> tuple[List[Dict[str, str]], Optional[List[Dict]], Optional[str]]:
    """
    Build message list for LLM API call with automatic compression.
    Uses compression_points to skip already-compressed messages.
    Returns (messages, tools, command_skill) tuple.
    command_skill is set when user used /command mode (e.g. "/trader-diagnosis").
    """
    from services.ai_context_compression_service import (
        compress_messages, update_compression_points,
        restore_tool_calls_to_messages,
        get_last_compression_point, filter_messages_by_compression,
    )

    messages = []

    # Load user profile (used for both skill filtering and personalization)
    profile = get_or_create_profile(db)

    # System prompt with Skill metadata injection
    system_prompt = load_system_prompt()

    # Inject available skills into system prompt (Level 1: metadata only)
    from services.hyper_ai_skill_engine import (
        scan_all_skills, get_enabled_skills, build_skills_metadata_prompt
    )
    all_skills = scan_all_skills()
    enabled_skills = get_enabled_skills(all_skills, profile.enabled_skills)
    skills_prompt = build_skills_metadata_prompt(enabled_skills)
    system_prompt = system_prompt.replace("{available_skills}", skills_prompt)

    # /Command mode: detect /skill_name or /shortcut prefix and inject full SKILL.md
    command_skill = None
    skill_injection = None  # Will be inserted as separate system msg before user msg
    # Build lookup maps: name -> name, shortcut -> name
    skill_lookup = {}
    for s in enabled_skills:
        skill_lookup[s["name"]] = s["name"]
        if s.get("shortcut"):
            skill_lookup[s["shortcut"]] = s["name"]
    if user_message.startswith("/"):
        parts = user_message.split(None, 1)
        candidate = parts[0][1:]  # strip leading /
        resolved_name = skill_lookup.get(candidate)
        if resolved_name:
            from services.hyper_ai_skill_engine import load_skill
            skill_result = load_skill(resolved_name)
            if skill_result.get("success"):
                command_skill = resolved_name
                skill_injection = (
                    f"[Active Skill: {resolved_name}]\n"
                    f"The user triggered this skill via /{candidate} command. "
                    f"You MUST follow the workflow below step by step, "
                    f"executing ALL phases and checkpoints.\n\n"
                    f"{skill_result['content']}"
                )
                user_message = parts[1].strip() if len(parts) > 1 else "Please start this skill workflow."

    messages.append({"role": "system", "content": system_prompt})

    # Get profile context for personalization
    if profile.onboarding_completed:
        profile_context = _build_profile_context(profile)
        if profile_context:
            messages.append({
                "role": "system",
                "content": f"User Profile:\n{profile_context}"
            })

    # Inject long-term memories into context
    memory_context = _build_memory_context(db)
    if memory_context:
        messages.append({
            "role": "system",
            "content": memory_context
        })

    # Check compression points - load summary instead of old messages
    conversation = db.query(HyperAiConversation).filter(
        HyperAiConversation.id == conversation_id
    ).first()
    cp = get_last_compression_point(conversation) if conversation else None

    if cp and cp.get("summary"):
        messages.append({
            "role": "system",
            "content": f"[Previous conversation summary]\n{cp['summary']}"
        })

    # Load history messages (ORM objects for id-based filtering)
    history_orm = db.query(HyperAiMessage).filter(
        HyperAiMessage.conversation_id == conversation_id
    ).order_by(HyperAiMessage.created_at).limit(100).all()

    # Filter by compression point
    history_orm = filter_messages_by_compression(history_orm, cp)

    last_message_id = history_orm[-1].id if history_orm else None

    # Convert to dicts and restore tool calls
    api_format = api_config.get("api_format", "openai")
    history_dicts = [
        {
            "role": m.role,
            "content": m.content,
            "tool_calls_log": m.tool_calls_log,
            "reasoning_snapshot": m.reasoning_snapshot,
        }
        for m in history_orm
    ]
    restored_history = restore_tool_calls_to_messages(history_dicts, api_format, model=api_config.get("model", ""))
    messages.extend(restored_history)

    # Current user message — if /command mode matched, the last message in
    # restored_history is the raw "/health" saved by stream_chat_response.
    # Replace it with the parsed user_message instead of appending a duplicate.
    if command_skill and messages and messages[-1].get("role") == "user":
        messages[-1]["content"] = user_message
    else:
        messages.append({"role": "user", "content": user_message})

    # For new conversations (no history), inject the configured init image into
    # the first user message so the AI has visual context from the very start.
    if not history_orm:
        init_image_path = os.getenv("HYPER_AI_INIT_IMAGE", "").strip()
        if init_image_path and os.path.exists(init_image_path):
            try:
                import base64 as _b64
                ext = os.path.splitext(init_image_path)[1].lower().lstrip(".")
                mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
                with open(init_image_path, "rb") as _f:
                    img_b64 = _b64.b64encode(_f.read()).decode()
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user" and isinstance(messages[i].get("content"), str):
                        messages[i]["content"] = [
                            {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{img_b64}"}},
                            {"type": "text", "text": messages[i]["content"]},
                        ]
                        break
            except Exception as _img_err:
                print(f"[hyper_ai] Failed to inject init image: {_img_err}")

    # Inject skill workflow as a separate system message right before user message.
    # Placed here (not in system prompt) so it's the last thing AI reads before
    # the user's request, giving it highest attention weight.
    if skill_injection:
        user_msg = messages.pop()  # temporarily remove user msg
        messages.append({"role": "system", "content": skill_injection})
        messages.append(user_msg)  # put user msg back at the end

    # Apply compression if needed
    result = compress_messages(messages, api_config, db=db)
    messages = result["messages"]

    # Update compression_points if compression occurred
    if result["compressed"] and result["summary"] and last_message_id:
        if conversation:
            update_compression_points(
                conversation, last_message_id,
                result["summary"], result["compressed_at"], db
            )

    # Return tools if requested (OpenAI format; Anthropic conversion happens in stream_chat_response)
    tools = HYPER_AI_TOOLS if include_tools else None

    return messages, tools, command_skill


def _build_profile_context(profile: HyperAiProfile) -> str:
    """Build profile context string for system prompt."""
    parts = []
    if profile.trading_style:
        parts.append(f"Trading Style: {profile.trading_style}")
    if profile.risk_preference:
        parts.append(f"Risk Preference: {profile.risk_preference}")
    if profile.experience_level:
        parts.append(f"Experience Level: {profile.experience_level}")
    if profile.preferred_symbols:
        parts.append(f"Preferred Symbols: {profile.preferred_symbols}")
    if profile.preferred_timeframe:
        parts.append(f"Preferred Timeframe: {profile.preferred_timeframe}")
    if profile.capital_scale:
        parts.append(f"Capital Scale: {profile.capital_scale}")
    return "\n".join(parts)


def _build_memory_context(db: Session) -> str:
    """
    Build long-term memory context for system prompt injection.
    Groups memories by category for readability.
    """
    from services.hyper_ai_memory_service import get_memories, MAX_MEMORIES

    memories = get_memories(db, limit=MAX_MEMORIES)
    if not memories:
        return ""

    # Group by category
    groups: Dict[str, List[str]] = {}
    category_labels = {
        "preference": "Trading Preferences",
        "decision": "Key Decisions",
        "lesson": "Lessons Learned",
        "insight": "Market Insights",
        "context": "Context",
    }

    for m in memories:
        cat = m.get("category", "context")
        label = category_labels.get(cat, cat.title())
        if label not in groups:
            groups[label] = []
        groups[label].append(m["content"])

    parts = ["Long-term Memory (insights from past conversations):"]
    for label, items in groups.items():
        parts.append(f"\n[{label}]")
        for item in items:
            parts.append(f"- {item}")

    return "\n".join(parts)
