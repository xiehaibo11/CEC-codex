"""Shared LLM request helper for Hyper AI memory workflows."""

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def call_memory_llm(
    prompt: str,
    api_config: Dict[str, Any],
    *,
    max_tokens: int,
    purpose: str,
    log_incomplete_config: bool = False,
) -> Optional[str]:
    """Call the configured LLM and return the response text."""
    base_url = api_config.get("base_url", "")
    api_key = api_config.get("api_key", "")
    model = api_config.get("model", "")
    api_format = api_config.get("api_format", "openai")

    if not all([base_url, api_key, model]):
        if log_incomplete_config:
            logger.warning(f"[Memory] Incomplete API config for {purpose.lower()}")
        return None

    try:
        from services.ai_decision_service import (
            build_chat_completion_endpoints,
            build_llm_headers,
            build_llm_payload,
        )

        endpoints = build_chat_completion_endpoints(base_url, model)
        if api_format == "anthropic":
            endpoint = endpoints[0] if endpoints else f"{base_url.rstrip('/')}/messages"
        else:
            endpoint = endpoints[0] if endpoints else f"{base_url}/chat/completions"

        headers = build_llm_headers(api_format, api_key, base_url)
        body = build_llm_payload(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            api_format=api_format,
            max_tokens=max_tokens,
            temperature=None,
        )

        response = requests.post(endpoint, headers=headers, json=body, timeout=60)

        if response.status_code != 200:
            logger.warning(
                f"[Memory] {purpose} API error: status={response.status_code}, "
                f"body={response.text[:500]}"
            )
            return None

        try:
            data = response.json()
        except ValueError as e:
            logger.warning(f"[Memory] {purpose} response JSON parse error: {e}")
            return None

        if api_format == "anthropic":
            content = data.get("content", [])
            return content[0].get("text", "") if content else ""

        choices = data.get("choices", [])
        return choices[0].get("message", {}).get("content", "") if choices else ""

    except requests.exceptions.Timeout:
        logger.warning(f"[Memory] {purpose} API timeout (60s)")
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"[Memory] {purpose} API connection error: {e}")
    except Exception as e:
        logger.warning(f"[Memory] {purpose} unexpected error: {type(e).__name__}: {e}")

    return None
