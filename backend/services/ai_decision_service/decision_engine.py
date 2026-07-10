"""AI trading decision engine: call_ai_for_decision orchestration.

Builds the prompt, invokes the configured LLM provider, and parses the response
into a decision payload. Decision/parsing/persistence logic is unchanged.
"""
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from database.models import Account
from services.news_feed import fetch_latest_news
from services.system_logger import system_logger
from repositories import prompt_repo

from services.ai_decision_service.constants import SUPPORTED_SYMBOLS, SafeDict
from services.ai_decision_service.prompt_formatting import _build_multi_symbol_sampling_data
from services.ai_decision_service.prompt_context import _build_prompt_context
from services.ai_decision_service.llm_payload import (
    build_llm_headers,
    build_llm_payload,
)
from services.ai_decision_service.llm_models import (
    build_chat_completion_endpoints,
    is_reasoning_model,
    requires_deepseek_reasoning_content,
)
from services.ai_decision_service.persistence import _is_default_api_key
from services.ai_decision_service.decision_response import (
    build_structured_decisions,
    extract_response_text,
    normalize_decision_entries,
    parse_decision_payload,
    parse_streaming_response,
)

logger = logging.getLogger(__name__)


def call_ai_for_decision(
    db: Session,
    account: Account,
    portfolio: Dict,
    prices: Dict[str, float],
    samples: Optional[List] = None,
    target_symbol: Optional[str] = None,
    symbols: Optional[List[str]] = None,
    hyperliquid_state: Optional[Dict[str, Any]] = None,
    symbol_metadata: Optional[Dict[str, Any]] = None,
    trigger_context: Optional[Dict[str, Any]] = None,
    exchange: str = "hyperliquid",
) -> Optional[List[Dict[str, Any]]]:
    """Call AI model API to get trading decision

    Args:
        db: Database session
        account: Trading account
        portfolio: Portfolio data
        prices: Market prices
        samples: Legacy single-symbol samples (deprecated, use symbols instead)
        target_symbol: Legacy single symbol (deprecated, use symbols instead)
        symbols: List of symbols to include sampling data for (preferred method)
        hyperliquid_state: Optional Hyperliquid account state for real trading
        symbol_metadata: Optional mapping of symbol -> display name overrides
        trigger_context: Optional context about what triggered this decision (signal or scheduled)
        exchange: Exchange to use for market data ("hyperliquid" or "binance")
    """
    # Check if this is a default API key
    if _is_default_api_key(account.api_key):
        logger.info(f"Skipping AI trading for account {account.name} - using default API key")
        return None

    # IMPORTANT: Get global trading mode at the start
    from services.hyperliquid_environment import get_global_trading_mode
    global_environment = get_global_trading_mode(db)

    try:
        news_summary = fetch_latest_news()
        news_section = news_summary if news_summary else "No recent CoinJournal news available."
    except Exception as err:  # pragma: no cover - defensive logging
        logger.warning("Failed to fetch latest news: %s", err)
        news_section = "No recent CoinJournal news available."

    template = prompt_repo.get_prompt_for_account(db, account.id)
    if not template:
        logger.warning(
            "No prompt binding for account %s (%s), skipping AI decision",
            account.id, account.name
        )
        return None

    # Build context with multi-symbol support
    active_symbol_metadata = symbol_metadata or SUPPORTED_SYMBOLS
    symbol_order = symbols if symbols else list(active_symbol_metadata.keys())

    if symbols:
        # New multi-symbol approach
        from services.sampling_pool import sampling_pool
        from database.connection import SessionLocal
        from database.models import GlobalSamplingConfig

        # Get actual sampling interval from config
        sampling_interval = None
        try:
            with SessionLocal() as db:
                config = db.query(GlobalSamplingConfig).first()
                if config:
                    sampling_interval = config.sampling_interval
        except Exception as e:
            logger.warning(f"Failed to get sampling interval: {e}")

        sampling_data = _build_multi_symbol_sampling_data(symbols, sampling_pool, sampling_interval)
        context = _build_prompt_context(
            account,
            portfolio,
            prices,
            news_section,
            None,
            None,
            hyperliquid_state,
            db=db,
            symbol_metadata=active_symbol_metadata,
            symbol_order=symbol_order,
            sampling_interval=sampling_interval,
            environment=global_environment,
            template_text=template.template_text,
            trigger_context=trigger_context,
            exchange=exchange,
        )
        context["sampling_data"] = sampling_data
    else:
        # Legacy single-symbol approach (backward compatibility)
        # Get actual sampling interval from config
        sampling_interval = None
        try:
            from database.connection import SessionLocal
            from database.models import GlobalSamplingConfig
            with SessionLocal() as db:
                config = db.query(GlobalSamplingConfig).first()
                if config:
                    sampling_interval = config.sampling_interval
        except Exception as e:
            logger.warning(f"Failed to get sampling interval: {e}")

        context = _build_prompt_context(
            account,
            portfolio,
            prices,
            news_section,
            samples,
            target_symbol,
            hyperliquid_state,
            db=db,
            symbol_metadata=active_symbol_metadata,
            symbol_order=symbol_order,
            sampling_interval=sampling_interval,
            environment=global_environment,
            template_text=template.template_text,
            trigger_context=trigger_context,
            exchange=exchange,
        )

    # Market Regime variables are now generated inside _build_prompt_context

    try:
        prompt = template.template_text.format_map(SafeDict(context))
    except Exception as exc:  # pragma: no cover - fallback rendering
        logger.error("Failed to render prompt template '%s': %s", template.key, exc)
        prompt = template.template_text

    # System hard facts go LAST (U-shaped attention: the tail is the other
    # high-attention slot). Frozen directions, margin state, news-age rule.
    try:
        from services.ai_decision_service.prompt_runtime_sections import (
            build_critical_constraints_tail,
        )

        margin_usage = None
        if hyperliquid_state:
            margin_usage = hyperliquid_state.get("margin_usage_percent")
        constraints_tail = build_critical_constraints_tail(
            db, account.id, symbol_order, margin_usage_percent=margin_usage
        )
        if constraints_tail:
            prompt = f"{prompt}\n\n{constraints_tail}"
    except Exception as tail_err:  # noqa: BLE001 - advisory tail must not block decisions
        logger.warning("Failed to build critical constraints tail: %s", tail_err)

    logger.debug("Using prompt template '%s' for account %s", template.key, account.id)

    # Use unified payload/headers builders (see build_llm_payload docstring)
    headers = build_llm_headers("openai", account.api_key)

    # Enable streaming for DeepSeek reasoning models to handle high-load scenarios
    use_streaming = requires_deepseek_reasoning_content(account.model)

    payload = build_llm_payload(
        model=account.model,
        messages=[{"role": "user", "content": prompt}],
        api_format="openai",
        stream=use_streaming,
    )

    endpoints = build_chat_completion_endpoints(account.base_url, account.model)
    if not endpoints:
        logger.error("No valid API endpoint built for account %s", account.name)
        system_logger.log_error(
            "API_ENDPOINT_BUILD_FAILED",
            f"Failed to build API endpoint for {account.name} (model: {account.model})",
            {"account": account.name, "model": account.model, "base_url": account.base_url},
        )
        return None

    # Self-consistency gate: sample the same prompt N times (temperature 0.7
    # gives natural variance) and only keep directions the samples agree on.
    # Verified research (arXiv 2505.06120): LLM decision degradation is mostly
    # run-to-run variance - exactly what direction-agreement voting removes.
    from services.ai_decision_service.self_consistency import (
        configured_samples,
        reconcile_decision_samples,
    )

    n_samples = configured_samples()
    samples = []
    for sample_idx in range(n_samples):
        decisions = _request_and_parse_decisions(
            account, prompt, headers, payload, endpoints, use_streaming
        )
        if decisions:
            samples.append(decisions)
        elif sample_idx == 0:
            # Primary sample failure keeps the original single-shot contract.
            return None
    if not samples:
        return None

    structured_decisions = reconcile_decision_samples(samples)
    logger.info(
        "AI decisions for %s (%s/%s self-consistency samples): %s",
        account.name, len(samples), n_samples, structured_decisions,
    )
    return structured_decisions


def _request_and_parse_decisions(
    account,
    prompt: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    endpoints,
    use_streaming: bool,
) -> Optional[List[Dict[str, Any]]]:
    """One LLM round trip: retry across endpoints, parse, and structure the
    decision entries. Returns None on any failure (caller decides policy)."""
    try:
        # Retry logic for rate limiting and transient errors
        max_retries = 3
        response = None
        success = False

        # Reasoning models need longer timeout (they think more, respond slower)
        if is_reasoning_model(account.model):
            request_timeout = 240
        else:
            request_timeout = 120

        for endpoint in endpoints:
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=request_timeout,
                        verify=False,  # Disable SSL verification for custom AI endpoints
                        stream=use_streaming,  # Enable streaming for DeepSeek V4/Reasoner
                    )

                    if response.status_code == 200:
                        success = True
                        break  # Success, exit retry loop

                    if response.status_code == 429:
                        # Rate limited, wait and retry
                        wait_time = (2**attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                        logger.warning(
                            "AI API rate limited for %s (attempt %s/%s), waiting %.1fs…",
                            account.name,
                            attempt + 1,
                            max_retries,
                            wait_time,
                        )
                        if attempt < max_retries - 1:
                            time.sleep(wait_time)
                            continue

                        logger.error(
                            "AI API rate limited after %s attempts for endpoint %s: %s",
                            max_retries,
                            endpoint,
                            response.text,
                        )
                        break

                    logger.warning(
                        "AI API returned status %s for endpoint %s: %s",
                        response.status_code,
                        endpoint,
                        response.text,
                    )
                    break  # Try next endpoint if available
                except requests.RequestException as req_err:
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        logger.warning(
                            "AI API request failed for endpoint %s (attempt %s/%s), retrying in %.1fs: %s",
                            endpoint,
                            attempt + 1,
                            max_retries,
                            wait_time,
                            req_err,
                        )
                        time.sleep(wait_time)
                        continue

                    logger.warning(
                        "AI API request failed after %s attempts for endpoint %s: %s",
                        max_retries,
                        endpoint,
                        req_err,
                    )
                    break
            if success:
                break

        if not success or not response:
            logger.error("All API endpoints failed for account %s (%s)", account.name, account.model)
            system_logger.log_error(
                "AI_API_ALL_ENDPOINTS_FAILED",
                f"All API endpoints failed for {account.name}",
                {
                    "account": account.name,
                    "model": account.model,
                    "endpoints_tried": [str(ep) for ep in endpoints],
                    "max_retries": max_retries,
                },
            )
            return None

        result = parse_streaming_response(response) if use_streaming else response.json()
        if not result:
            return None

        text_content, reasoning_text, api_reasoning_content = extract_response_text(result)
        if not text_content:
            return None

        parsed_decision = parse_decision_payload(text_content)
        if not parsed_decision:
            return None

        decision, cleaned_content, raw_decision_text = parsed_decision
        decision_entries = normalize_decision_entries(decision)
        if decision_entries is None:
            return None

        snapshot_source = cleaned_content or raw_decision_text
        structured_decisions = build_structured_decisions(
            decision_entries,
            account.name,
            prompt,
            api_reasoning_content,
            reasoning_text,
            snapshot_source,
        )
        if not structured_decisions:
            logger.error("AI response for %s contained no usable decision entries", account.name)
            return None

        return structured_decisions

    except requests.RequestException as err:
        logger.error(f"AI API request failed: {err}")
        return None
    except json.JSONDecodeError as err:
        logger.error(f"Failed to parse AI response as JSON: {err}")
        # Try to log the content that failed to parse
        try:
            if 'text_content' in locals():
                logger.error(f"Content that failed to parse: {text_content[:500]}")
        except Exception:
            pass
        return None
    except Exception as err:
        logger.error(f"Unexpected error calling AI: {err}", exc_info=True)
        return None
