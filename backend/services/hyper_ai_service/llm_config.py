"""Hyper AI user profile and LLM provider configuration.

Profile retrieval/creation plus reading, testing, and saving the user's LLM
provider credentials. Credentials are stored encrypted on the profile.
"""
import logging
from typing import Any, Dict, Optional

import requests
from sqlalchemy.orm import Session

from database.models import HyperAiProfile
from services.ai_decision_service import (
    detect_api_format,
    build_llm_payload,
    build_llm_headers,
)
from services.hyper_ai_llm_providers import get_provider
from utils.encryption import decrypt_private_key

logger = logging.getLogger(__name__)


def get_or_create_profile(db: Session) -> HyperAiProfile:
    """Get existing profile or create a new one (single-user system)."""
    profile = db.query(HyperAiProfile).first()
    if not profile:
        profile = HyperAiProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_llm_config(db: Session) -> Dict[str, Any]:
    """Get LLM configuration from user profile."""
    profile = get_or_create_profile(db)

    if not profile.llm_provider:
        return {"configured": False}

    # Get provider preset or use custom config
    provider = get_provider(profile.llm_provider)
    base_url = profile.llm_base_url or (provider.base_url if provider else "")
    model = profile.llm_model or (provider.models[0] if provider and provider.models else "")

    # Decrypt API key
    api_key = None
    if profile.llm_api_key_encrypted:
        try:
            api_key = decrypt_private_key(profile.llm_api_key_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")

    # Detect API format from URL for custom provider
    if profile.llm_provider == "custom" and base_url:
        _, api_format = detect_api_format(base_url)
        api_format = api_format or "openai"
    else:
        api_format = provider.api_format if provider else "openai"

    return {
        "configured": True,
        "provider": profile.llm_provider,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "api_format": api_format
    }


def test_llm_connection(
    provider: str,
    api_key: str,
    model: str,
    base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Test LLM connection by making a simple API call.
    Returns {"success": True} or {"success": False, "error": "message"}
    """
    # Get provider config
    provider_config = get_provider(provider)

    if provider == "custom":
        if not base_url:
            return {"success": False, "error": "Base URL is required for custom provider"}
        # Auto-detect API format from URL (same as AI Trader)
        url, api_format = detect_api_format(base_url)
        if not url:
            return {"success": False, "error": "Invalid Base URL"}
        api_format = api_format or "openai"
    else:
        if not provider_config:
            return {"success": False, "error": f"Unknown provider: {provider}"}
        effective_base_url = base_url or provider_config.base_url
        api_format = provider_config.api_format
        # Build URL based on api_format
        if api_format == "anthropic":
            url = f"{effective_base_url.rstrip('/')}/messages"
        else:
            url = f"{effective_base_url.rstrip('/')}/chat/completions"

    if not model:
        model = provider_config.models[0] if provider_config and provider_config.models else "gpt-3.5-turbo"

    try:
        # Use unified headers/payload builders (see build_llm_payload in ai_decision_service)
        headers = build_llm_headers(api_format, api_key, url)
        payload = build_llm_payload(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            api_format=api_format,
            max_tokens=10,
        )

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            return {"success": True}
        else:
            error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
            # Try to extract error message from JSON
            try:
                err_json = response.json()
                if "error" in err_json:
                    if isinstance(err_json["error"], dict):
                        error_msg = err_json["error"].get("message", error_msg)
                    else:
                        error_msg = str(err_json["error"])
            except:
                pass
            return {"success": False, "error": error_msg}

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Connection timeout"}
    except requests.exceptions.ConnectionError as e:
        return {"success": False, "error": f"Connection failed: {str(e)[:100]}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def save_llm_config(
    db: Session,
    provider: str,
    api_key: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None
) -> HyperAiProfile:
    """Save LLM configuration to user profile."""
    from utils.encryption import encrypt_private_key

    profile = get_or_create_profile(db)
    profile.llm_provider = provider
    profile.llm_model = model
    profile.llm_base_url = base_url

    if api_key:
        profile.llm_api_key_encrypted = encrypt_private_key(api_key)

    db.commit()
    db.refresh(profile)
    return profile
