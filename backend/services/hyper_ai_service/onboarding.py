"""Hyper AI onboarding chat flow.

A simplified streaming chat (no tools, no memory) used to collect the user's
trading profile, plus the helpers that parse the [PROFILE_DATA] block the AI
emits and persist it to the profile.
"""
import json
import logging
import time
from typing import Dict, Generator, Optional

import requests
from sqlalchemy.orm import Session

from services.ai_decision_service import (
    build_chat_completion_endpoints,
    build_llm_payload,
    build_llm_headers,
    strip_thinking_tags,
)
from services.ai_stream_service import (
    get_buffer_manager,
    generate_task_id,
    run_ai_task_in_background,
    format_sse_event,
)

from services.hyper_ai_service.conversations import (
    get_conversation_messages,
    save_message,
)
from services.hyper_ai_service.llm_config import get_llm_config, get_or_create_profile
from services.hyper_ai_service.prompts import load_onboarding_prompt
from services.hyper_ai_service.retry import API_MAX_RETRIES, _get_retry_delay

logger = logging.getLogger(__name__)


def stream_onboarding_response(
    db: Session,
    conversation_id: int,
    user_message: str,
    lang: str = "en"
) -> Generator[str, None, None]:
    """Stream onboarding chat response - simplified version for profile collection."""
    llm_config = get_llm_config(db)
    if not llm_config.get("configured"):
        yield format_sse_event("error", {"message": "LLM not configured"})
        return

    # Handle greeting request - AI initiates conversation
    is_greeting = user_message == "__GREETING__"
    if is_greeting:
        user_message = "请用中文介绍你自己并开始引导对话。" if lang == "zh" else "Please introduce yourself and start the onboarding conversation."
    else:
        # Save user message (don't save the greeting trigger)
        save_message(db, conversation_id, "user", user_message)

    # Build messages with onboarding prompt (language-specific)
    messages = []
    system_prompt = load_onboarding_prompt(lang)
    messages.append({"role": "system", "content": system_prompt})

    # Get conversation history (skip for greeting)
    if not is_greeting:
        history = get_conversation_messages(db, conversation_id, limit=20)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    # Make API call (reuse existing logic)
    base_url = llm_config["base_url"]
    model = llm_config["model"]
    api_key = llm_config["api_key"]
    api_format = llm_config.get("api_format", "openai")

    endpoints = build_chat_completion_endpoints(base_url, model)
    if not endpoints:
        yield format_sse_event("error", {"message": "Invalid API endpoint"})
        return

    # Use unified headers/payload builders (see build_llm_payload in ai_decision_service)
    headers = build_llm_headers(api_format, api_key, base_url)

    body = build_llm_payload(
        model=model,
        messages=messages,
        api_format=api_format,
        stream=True,
    )

    response = None
    for attempt in range(API_MAX_RETRIES):
        for endpoint in endpoints:
            try:
                response = requests.post(
                    endpoint, headers=headers, json=body,
                    stream=True, timeout=120
                )
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                continue
        if response and response.status_code == 200:
            break
        time.sleep(_get_retry_delay(attempt))

    if not response or response.status_code != 200:
        yield format_sse_event("error", {"message": "API request failed"})
        return

    yield from _process_onboarding_stream_response(db, conversation_id, response, api_format)


def start_onboarding_chat_task(
    db: Session,
    conversation_id: int,
    user_message: str,
    lang: str = None
) -> str:
    """Start an onboarding chat task in background."""
    task_id = generate_task_id("onboard")
    manager = get_buffer_manager()
    manager.create_task(task_id, conversation_id)

    # Default to English if not specified
    effective_lang = lang or "en"

    def generator_func():
        from database.connection import SessionLocal
        task_db = SessionLocal()
        try:
            yield from stream_onboarding_response(task_db, conversation_id, user_message, effective_lang)
        finally:
            task_db.close()

    run_ai_task_in_background(task_id, generator_func)
    return task_id


def _parse_profile_data(content: str) -> Optional[Dict[str, str]]:
    """Parse [PROFILE_DATA]...[COMPLETE] block from AI response with tolerance."""
    import re

    # Try multiple patterns for tolerance (different AI models may vary)
    patterns = [
        r'\[PROFILE_DATA\](.*?)\[COMPLETE\]',
        r'\[PROFILE_DATA\](.*?)\[/COMPLETE\]',
        r'\[PROFILE\](.*?)\[COMPLETE\]',
        r'\[PROFILE\](.*?)\[/PROFILE\]',
        r'```\s*\[PROFILE_DATA\](.*?)\[COMPLETE\]\s*```',  # In code block
    ]

    block = None
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            block = match.group(1).strip()
            break

    if not block:
        return None

    data = {}
    for line in block.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            # Normalize common key variations
            if key in ['name', 'nickname', 'nick', '称呼', '昵称']:
                key = 'nickname'
            elif key in ['exp', 'experience', '经验', '交易经验']:
                key = 'experience'
            elif key in ['risk', 'risk_preference', '风险', '风险偏好']:
                key = 'risk'
            elif key in ['style', 'trading_style', '风格', '交易风格']:
                key = 'style'
            data[key] = value

    return data if data else None


def _strip_profile_markers(content: str) -> str:
    """Remove [PROFILE_DATA]...[COMPLETE] block from content for display."""
    import re

    # Remove various formats of profile data blocks
    patterns = [
        r'\[PROFILE_DATA\].*?\[COMPLETE\]',
        r'\[PROFILE_DATA\].*?\[/COMPLETE\]',
        r'\[PROFILE\].*?\[COMPLETE\]',
        r'\[PROFILE\].*?\[/PROFILE\]',
        r'```\s*\[PROFILE_DATA\].*?\[COMPLETE\]\s*```',
    ]

    cleaned = content
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)

    # Clean up extra whitespace
    cleaned = cleaned.strip()

    return cleaned


def _save_profile_from_onboarding(db: Session, profile_data: Dict[str, str]) -> None:
    """Save parsed profile data to database."""
    profile = get_or_create_profile(db)

    # Save nickname to profile
    nickname = profile_data.get('nickname', '')
    if nickname:
        profile.nickname = nickname

    # Save profile fields (natural language descriptions)
    if profile_data.get('experience'):
        profile.experience_level = profile_data['experience']

    if profile_data.get('risk'):
        profile.risk_preference = profile_data['risk']

    if profile_data.get('style'):
        style = profile_data['style']
        if style.lower() not in ['未提及', 'not mentioned']:
            profile.trading_style = style

    # Mark onboarding as completed
    profile.onboarding_completed = True

    db.commit()
    logger.info(f"Saved onboarding profile: nickname={nickname}, experience={profile.experience_level}")


def _process_onboarding_stream_response(
    db: Session,
    conversation_id: int,
    response: requests.Response,
    api_format: str
) -> Generator[str, None, None]:
    """Process streaming response for onboarding, handling profile data extraction."""
    content_parts = []
    reasoning_parts = []

    try:
        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode('utf-8')
            if not line_str.startswith('data: '):
                continue

            data_str = line_str[6:]
            if data_str == '[DONE]':
                break

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # Extract content based on API format
            if api_format == "anthropic":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        content_parts.append(text)
                        yield format_sse_event("content", {"text": text})
            else:
                # OpenAI format
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        content_parts.append(text)
                        yield format_sse_event("content", {"text": text})

                    reasoning = delta.get("reasoning_content", "")
                    if reasoning:
                        reasoning_parts.append(reasoning)
                        yield format_sse_event("reasoning", {"text": reasoning})

        # Process full content
        full_content = "".join(content_parts)
        full_reasoning = "".join(reasoning_parts) if reasoning_parts else None

        # Strip <thinking> text tags from content (some proxies embed them)
        full_content, tag_thinking = strip_thinking_tags(full_content)
        if tag_thinking:
            full_reasoning = (full_reasoning + "\n\n" + tag_thinking).strip() if full_reasoning else tag_thinking

        # Check for profile data completion
        profile_data = _parse_profile_data(full_content)
        onboarding_complete = False

        if profile_data:
            # Save profile to database
            _save_profile_from_onboarding(db, profile_data)
            onboarding_complete = True

            # Strip markers from content for display
            display_content = _strip_profile_markers(full_content)
        else:
            display_content = full_content

        # Save assistant message (without profile markers)
        if display_content:
            save_message(
                db, conversation_id, "assistant", display_content,
                reasoning_snapshot=full_reasoning,
                is_complete=True
            )

        yield format_sse_event("done", {
            "conversation_id": conversation_id,
            "content_length": len(display_content),
            "onboarding_complete": onboarding_complete
        })

    except Exception as e:
        logger.error(f"Onboarding stream processing error: {e}", exc_info=True)
        yield format_sse_event("error", {"message": str(e)})
