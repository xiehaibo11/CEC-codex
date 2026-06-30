"""Suggested-questions generation for the Hyper AI welcome screen.

Gathers user context, prompts the configured LLM for 3 follow-up questions, and
caches them on the profile with an async background refresh when stale.
"""
import json
import logging
import threading
from typing import Any, Dict, List

import requests
from sqlalchemy.orm import Session

from database.models import HyperAiConversation, HyperAiMessage
from services.ai_decision_service import (
    build_chat_completion_endpoints,
    build_llm_payload,
    build_llm_headers,
)
from services.ai_stream_service import submit_ai_background_task

from services.hyper_ai_service.llm_config import get_or_create_profile, get_llm_config

logger = logging.getLogger(__name__)

SUGGESTION_CACHE_HOURS = 6  # Update suggestions every 6 hours

_suggestions_update_lock = threading.Lock()
_suggestions_update_running = False


def get_suggestions_context(db: Session) -> Dict[str, Any]:
    """
    Gather context for generating suggested questions.
    Returns user profile, recent conversations, and configuration status.
    """
    from database.models import Account, SignalPool, HyperliquidWallet

    profile = get_or_create_profile(db)

    # Get recent 3 conversations (non-onboarding, non-bot)
    recent_convs = db.query(HyperAiConversation).filter(
        HyperAiConversation.is_onboarding == False,
        HyperAiConversation.is_bot_conversation == False
    ).order_by(HyperAiConversation.updated_at.desc()).limit(3).all()

    conversations_context = []
    for conv in recent_convs:
        # Get last 2 user messages and 2 assistant messages
        messages = db.query(HyperAiMessage).filter(
            HyperAiMessage.conversation_id == conv.id
        ).order_by(HyperAiMessage.created_at.desc()).limit(4).all()

        msg_snippets = []
        for msg in reversed(messages):
            content = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
            role_label = "User" if msg.role == "user" else "AI"
            msg_snippets.append(f"- {role_label}: {content}")

        if msg_snippets:
            conversations_context.append({
                "title": conv.title,
                "snippets": msg_snippets
            })

    # Get configuration status
    trader_count = db.query(Account).filter(
        Account.is_deleted == False,
        Account.account_type == "AI"
    ).count()

    signal_pool_count = db.query(SignalPool).count()

    wallet_count = db.query(HyperliquidWallet).count()

    return {
        "profile": {
            "nickname": profile.nickname,
            "trading_style": profile.trading_style,
            "risk_preference": profile.risk_preference,
            "experience_level": profile.experience_level,
            "preferred_symbols": profile.preferred_symbols,
        },
        "conversations": conversations_context,
        "config_status": {
            "trader_count": trader_count,
            "signal_pool_count": signal_pool_count,
            "wallet_count": wallet_count,
        }
    }


def build_suggestions_prompt(context: Dict[str, Any]) -> str:
    """
    Build prompt for generating suggested questions.
    """
    profile = context.get("profile", {})
    conversations = context.get("conversations", [])
    config_status = context.get("config_status", {})

    prompt_parts = ["Based on the following user context, generate 3 short questions the user might want to ask next.\n"]

    # User profile
    if any([profile.get("nickname"), profile.get("trading_style"), profile.get("experience_level")]):
        prompt_parts.append("User Profile:")
        if profile.get("nickname"):
            prompt_parts.append(f"- Name: {profile['nickname']}")
        if profile.get("experience_level"):
            prompt_parts.append(f"- Experience: {profile['experience_level']}")
        if profile.get("trading_style"):
            prompt_parts.append(f"- Style: {profile['trading_style']}")
        if profile.get("risk_preference"):
            prompt_parts.append(f"- Risk: {profile['risk_preference']}")
        prompt_parts.append("")

    # Configuration status
    prompt_parts.append("Current Setup:")
    prompt_parts.append(f"- AI Traders: {config_status.get('trader_count', 0)}")
    prompt_parts.append(f"- Signal Pools: {config_status.get('signal_pool_count', 0)}")
    prompt_parts.append(f"- Wallets: {config_status.get('wallet_count', 0)}")
    prompt_parts.append("")

    # Recent conversations
    if conversations:
        prompt_parts.append("Recent Conversations:")
        for conv in conversations:
            prompt_parts.append(f"\n[{conv['title']}]")
            for snippet in conv["snippets"]:
                prompt_parts.append(snippet)
        prompt_parts.append("")

    prompt_parts.append("---")
    prompt_parts.append("Generate 3 short, natural questions (max 30 chars each) the user might want to continue exploring.")
    prompt_parts.append("Use the same language as the user's recent conversations.")
    prompt_parts.append("Output ONLY a JSON array of 3 strings, no other text.")
    prompt_parts.append('Example: ["How is my BTC Trader doing?", "Create a new signal pool", "Explain leverage settings"]')

    return "\n".join(prompt_parts)


def generate_suggested_questions(db: Session) -> List[str]:
    """
    Generate suggested questions using the user's configured LLM.
    Returns empty list if LLM not configured or generation fails.
    """
    config = get_llm_config(db)
    if not config.get("configured"):
        return []

    context = get_suggestions_context(db)

    # No conversations = new user, return empty (frontend will show default questions)
    if not context.get("conversations"):
        return []

    prompt = build_suggestions_prompt(context)

    # Extract config values
    api_format = config.get("api_format", "openai")
    base_url = config.get("base_url", "")
    model = config.get("model", "")
    api_key = config.get("api_key", "")

    if not all([base_url, api_key, model]):
        logger.warning("[Suggestions] Incomplete LLM config")
        return []

    try:
        # Use unified LLM call pattern (same as hyper_ai_memory_service)
        endpoints = build_chat_completion_endpoints(base_url, model)
        if api_format == "anthropic":
            endpoint = endpoints[0] if endpoints else f"{base_url.rstrip('/')}/messages"
        else:
            endpoint = endpoints[0] if endpoints else f"{base_url.rstrip('/')}/chat/completions"

        headers = build_llm_headers(api_format, api_key, endpoint)
        body = build_llm_payload(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            api_format=api_format,
            max_tokens=150,
            temperature=0.7,
        )

        logger.info(f"[Suggestions] Calling LLM: {endpoint}, model: {model}")
        response = requests.post(endpoint, headers=headers, json=body, timeout=30)

        if response.status_code != 200:
            logger.warning(f"[Suggestions] LLM error: status={response.status_code}, body={response.text[:200]}")
            return []

        data = response.json()

        # Extract content (same pattern as memory service)
        if api_format == "anthropic":
            content_list = data.get("content", [])
            text = content_list[0].get("text", "") if content_list else ""
        else:
            choices = data.get("choices", [])
            text = choices[0].get("message", {}).get("content", "") if choices else ""

        if not text:
            logger.warning(f"[Suggestions] LLM returned empty content")
            return []

        # Parse JSON array from response
        text = text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        questions = json.loads(text)
        if isinstance(questions, list) and len(questions) >= 1:
            logger.info(f"[Suggestions] Generated {len(questions)} questions")
            return questions[:3]

        logger.warning(f"[Suggestions] Invalid response format: {text[:100]}")
        return []

    except requests.exceptions.Timeout:
        logger.warning("[Suggestions] LLM timeout (30s)")
        return []
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"[Suggestions] LLM connection error: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"[Suggestions] JSON parse error: {e}")
        return []
    except Exception as e:
        logger.warning(f"[Suggestions] Unexpected error: {type(e).__name__}: {e}")
        return []


def get_or_update_suggestions(db: Session) -> Dict[str, Any]:
    """
    Get cached suggestions or trigger async update if stale.
    Returns current suggestions (may be stale) and triggers background update.
    """
    from datetime import datetime, timedelta

    profile = get_or_create_profile(db)

    # Check if we have conversations at all
    conv_count = db.query(HyperAiConversation).filter(
        HyperAiConversation.is_onboarding == False,
        HyperAiConversation.is_bot_conversation == False
    ).count()

    if conv_count == 0:
        return {
            "suggestions": [],
            "is_new_user": True,
            "updated_at": None
        }

    # Parse cached suggestions
    cached_suggestions = []
    if profile.suggested_questions:
        try:
            cached_suggestions = json.loads(profile.suggested_questions)
        except:
            pass

    # Check if cache is stale
    cache_stale = True
    if profile.suggested_questions_at:
        cache_age = datetime.utcnow() - profile.suggested_questions_at
        cache_stale = cache_age > timedelta(hours=SUGGESTION_CACHE_HOURS)

    # If stale, trigger async update
    if cache_stale:
        with _suggestions_update_lock:
            global _suggestions_update_running
            if _suggestions_update_running:
                return {
                    "suggestions": cached_suggestions,
                    "is_new_user": False,
                    "updated_at": profile.suggested_questions_at.isoformat() if profile.suggested_questions_at else None
                }
            _suggestions_update_running = True

        def update_task():
            global _suggestions_update_running
            from database.connection import SessionLocal
            task_db = SessionLocal()
            try:
                questions = generate_suggested_questions(task_db)
                if questions:
                    task_profile = get_or_create_profile(task_db)
                    task_profile.suggested_questions = json.dumps(questions)
                    task_profile.suggested_questions_at = datetime.utcnow()
                    task_db.commit()
                    logger.info(f"Updated suggested questions: {questions}")
            except Exception as e:
                logger.error(f"Failed to update suggestions: {e}")
            finally:
                task_db.close()
                with _suggestions_update_lock:
                    _suggestions_update_running = False

        submit_ai_background_task(update_task)

    return {
        "suggestions": cached_suggestions,
        "is_new_user": False,
        "updated_at": profile.suggested_questions_at.isoformat() if profile.suggested_questions_at else None
    }
