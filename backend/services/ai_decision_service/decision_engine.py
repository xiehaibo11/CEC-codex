"""AI trading decision engine: call_ai_for_decision orchestration.

Builds the prompt, invokes the configured LLM provider, and parses the response
into a decision payload. Decision/parsing/persistence logic is unchanged.
"""
import json
import logging
import random
import re
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
    _extract_text_from_message,
    build_llm_headers,
    build_llm_payload,
)
from services.ai_decision_service.llm_models import (
    build_chat_completion_endpoints,
    is_reasoning_model,
    requires_deepseek_reasoning_content,
)
from services.ai_decision_service.persistence import _is_default_api_key

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

    try:
        endpoints = build_chat_completion_endpoints(account.base_url, account.model)
        if not endpoints:
            logger.error("No valid API endpoint built for account %s", account.name)
            system_logger.log_error(
                "API_ENDPOINT_BUILD_FAILED",
                f"Failed to build API endpoint for {account.name} (model: {account.model})",
                {"account": account.name, "model": account.model, "base_url": account.base_url},
            )
            return None

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

        # Handle streaming response for DeepSeek V4/Reasoner
        if use_streaming:
            try:
                full_content = ""
                reasoning_content = ""
                chunk_count = 0

                # Parse SSE stream
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')

                        # SSE format: "data: {...}"
                        if line_str.startswith('data: '):
                            json_str = line_str[6:]  # Remove "data: " prefix

                            # Check for [DONE] marker
                            if json_str.strip() == '[DONE]':
                                break

                            try:
                                data = json.loads(json_str)
                                chunk_count += 1

                                # Extract content from delta
                                if data.get('choices'):
                                    delta = data['choices'][0].get('delta', {})
                                    content = delta.get('content') or ''
                                    reasoning = delta.get('reasoning_content') or ''

                                    full_content += content
                                    reasoning_content += reasoning

                            except json.JSONDecodeError as e:
                                logger.warning(f"JSON decode error in streaming response: {e}")
                                continue

                # Construct complete response object (simulate non-streaming format)
                result = {
                    "choices": [{
                        "message": {
                            "content": full_content,
                            "reasoning_content": reasoning_content
                        },
                        "finish_reason": "stop"
                    }]
                }

                logger.info(f"Streaming response completed: {chunk_count} chunks, content: {len(full_content)} chars, reasoning: {len(reasoning_content)} chars")

            except Exception as stream_err:
                logger.error(f"Failed to parse streaming response: {stream_err}")
                return None
        else:
            # Non-streaming response (existing logic)
            result = response.json()

        # Extract text from OpenAI-compatible response format
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "")
            reasoning_text = _extract_text_from_message(message.get("reasoning"))

            # Extract reasoning content from multi-vendor protocols (defensive design)
            def _extract_reasoning_content_safe(api_result: dict) -> str:
                """
                Extract reasoning content from AI response (multi-vendor support)
                Supports: OpenAI (o1/o3/gpt-5), DeepSeek (R1), Qwen (QwQ), Claude (thinking), Gemini (thoughts), Grok (3-mini)
                Returns empty string on any error - never blocks main trading flow
                """
                try:
                    reasoning_parts = []

                    # Safe extraction: get choices and message with type checking
                    choices = api_result.get("choices")
                    if not choices or not isinstance(choices, list) or len(choices) == 0:
                        return ""

                    choice_item = choices[0]
                    if not isinstance(choice_item, dict):
                        return ""

                    msg = choice_item.get("message")
                    if not isinstance(msg, dict):
                        return ""

                    # Strategy 1: OpenAI/DeepSeek/Qwen/Grok standard format
                    # message.reasoning (OpenAI o1/o3/gpt-5)
                    # message.reasoning_content (DeepSeek V4/R1, Qwen QwQ, Grok 3-mini)
                    try:
                        reasoning_field = msg.get("reasoning")
                        if reasoning_field:
                            extracted = _extract_text_from_message(reasoning_field)
                            if extracted and extracted.strip():
                                reasoning_parts.append(extracted.strip())
                    except Exception:
                        pass

                    try:
                        reasoning_content_field = msg.get("reasoning_content")
                        if reasoning_content_field:
                            extracted = _extract_text_from_message(reasoning_content_field)
                            if extracted and extracted.strip():
                                reasoning_parts.append(extracted.strip())
                    except Exception:
                        pass

                    # Strategy 2: Claude format - thinking blocks in content array
                    # {"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]}
                    try:
                        content_array = msg.get("content")
                        if isinstance(content_array, list):
                            for block in content_array:
                                if isinstance(block, dict) and block.get("type") == "thinking":
                                    thinking_text = block.get("thinking")
                                    if thinking_text and isinstance(thinking_text, str) and thinking_text.strip():
                                        reasoning_parts.append(thinking_text.strip())
                    except Exception:
                        pass

                    # Strategy 3: Gemini format - parts array with thought=true flag
                    # {"parts": [{"text": "...", "thought": true}, {"text": "..."}]}
                    try:
                        parts_array = msg.get("parts")
                        if isinstance(parts_array, list):
                            for part in parts_array:
                                if isinstance(part, dict) and part.get("thought") is True:
                                    thought_text = part.get("text")
                                    if thought_text and isinstance(thought_text, str) and thought_text.strip():
                                        reasoning_parts.append(thought_text.strip())
                    except Exception:
                        pass

                    # Strategy 4: Fallback - try other possible field names
                    try:
                        for field_name in ["chain_of_thought", "cot", "thinking", "thinking_log", "reasoning_log"]:
                            field_value = msg.get(field_name)
                            if field_value:
                                extracted = _extract_text_from_message(field_value)
                                if extracted and extracted.strip():
                                    reasoning_parts.append(extracted.strip())
                                    break  # Only take first match from fallback fields
                    except Exception:
                        pass

                    # Merge all reasoning segments
                    if reasoning_parts:
                        merged = "\n\n--- [Reasoning Section] ---\n\n".join(reasoning_parts)
                        logger.debug(f"Reasoning content extracted: {len(merged)} chars from API response")
                        return merged

                    return ""

                except Exception as e:
                    logger.warning(f"Failed to extract reasoning content from API response: {e}")
                    return ""

            # Extract reasoning content for later merging
            api_reasoning_content = _extract_reasoning_content_safe(result)

            # Check if response was truncated due to length limit
            if finish_reason == "length":
                logger.warning("AI response was truncated due to token limit. Consider increasing max_tokens.")
                # Try to get content from reasoning field if available (some models put partial content there)
                raw_content = message.get("reasoning") or message.get("content")
            else:
                raw_content = message.get("content")

            text_content = _extract_text_from_message(raw_content)

            if not text_content and reasoning_text:
                # Some providers keep reasoning separately even on normal completion
                text_content = reasoning_text
            elif not text_content and api_reasoning_content:
                # Fallback: DeepSeek Reasoner may put JSON in reasoning_content
                text_content = api_reasoning_content
                logger.info("Using reasoning_content as fallback for empty content (DeepSeek Reasoner)")

            if not text_content:
                logger.error(
                    "Empty content in AI response: %s",
                    {k: v for k, v in result.items() if k != "usage"},
                )
                return None

            # Try to extract JSON from the text
            # Sometimes AI might wrap JSON in markdown code blocks
            raw_decision_text = text_content.strip()
            cleaned_content = raw_decision_text
            if "```json" in cleaned_content:
                cleaned_content = cleaned_content.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_content:
                cleaned_content = cleaned_content.split("```")[1].split("```")[0].strip()

            # Handle potential JSON parsing issues with escape sequences
            try:
                decision = json.loads(cleaned_content)
            except json.JSONDecodeError as parse_err:
                logger.warning("Initial JSON parse failed: %s", parse_err)
                logger.warning("Problematic content: %s...", cleaned_content[:200])

                cleaned = (
                    cleaned_content.replace("\n", " ")
                    .replace("\r", " ")
                    .replace("\t", " ")
                )
                cleaned = cleaned.replace("“", '"').replace("”", '"')
                cleaned = cleaned.replace("‘", "'").replace("’", "'")
                cleaned = cleaned.replace("–", "-").replace("—", "-").replace("‑", "-")

                try:
                    decision = json.loads(cleaned)
                    cleaned_content = cleaned
                    logger.info("Successfully parsed AI decision after cleanup")
                except json.JSONDecodeError:
                    logger.error("JSON parsing failed after cleanup, attempting manual extraction")
                    logger.error(f"Original AI response: {text_content[:1000]}...")
                    logger.error(f"Cleaned content: {cleaned[:1000]}...")
                    operation_match = re.search(r'"operation"\s*:\s*"([^"]+)"', text_content, re.IGNORECASE)
                    symbol_match = re.search(r'"symbol"\s*:\s*"([^"]+)"', text_content, re.IGNORECASE)
                    portion_match = re.search(r'"target_portion_of_balance"\s*:\s*([0-9.]+)', text_content)
                    reason_match = re.search(r'"reason"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', text_content, re.DOTALL)

                    if operation_match and symbol_match and portion_match:
                        decision = {
                            "operation": operation_match.group(1),
                            "symbol": symbol_match.group(1),
                            "target_portion_of_balance": float(portion_match.group(1)),
                            "reason": reason_match.group(1) if reason_match else "AI response parsing issue",
                        }
                        logger.info("Successfully recovered AI decision via manual extraction")
                        cleaned_content = json.dumps(decision)
                    else:
                        logger.error("Unable to extract required fields from AI response")
                        logger.error(f"Regex match results - operation: {operation_match.group(1) if operation_match else None}, symbol: {symbol_match.group(1) if symbol_match else None}, portion: {portion_match.group(1) if portion_match else None}, reason: {reason_match.group(1)[:100] if reason_match else None}...")
                        return None

            # Normalize into a list of decisions
            if isinstance(decision, dict) and isinstance(decision.get("decisions"), list):
                decision_entries = decision.get("decisions") or []
            elif isinstance(decision, list):
                decision_entries = decision
            elif isinstance(decision, dict):
                decision_entries = [decision]
            else:
                logger.error(f"AI response has unsupported structure: {type(decision)}")
                return None

            snapshot_source = cleaned_content if "cleaned_content" in locals() and cleaned_content else raw_decision_text

            structured_decisions: List[Dict[str, Any]] = []
            for idx, raw_entry in enumerate(decision_entries):
                if not isinstance(raw_entry, dict):
                    logger.warning(
                        "Skipping decision entry %s for account %s because it is %s instead of dict",
                        idx,
                        account.name,
                        type(raw_entry),
                    )
                    continue

                entry = dict(raw_entry)
                strategy_details = entry.get("trading_strategy")

                # Merge API reasoning content with trading_strategy
                # Priority: API reasoning (from reasoning models) > trading_strategy (from prompt) > fallback reasoning_text
                entry["_prompt_snapshot"] = prompt

                if api_reasoning_content:
                    # Reasoning model: merge trading_strategy and API reasoning content
                    base_strategy = strategy_details if isinstance(strategy_details, str) and strategy_details.strip() else ""
                    if base_strategy:
                        # Combine strategy description from JSON and real CoT from API (seamless merge)
                        entry["_reasoning_snapshot"] = f"{base_strategy}\n\n{api_reasoning_content}"
                    else:
                        # Only API reasoning content available
                        entry["_reasoning_snapshot"] = api_reasoning_content
                elif isinstance(strategy_details, str) and strategy_details.strip():
                    # Chat model: use trading_strategy from JSON
                    entry["_reasoning_snapshot"] = strategy_details.strip()
                else:
                    # Fallback: use reasoning_text extracted earlier
                    entry["_reasoning_snapshot"] = reasoning_text or ""

                entry["_raw_decision_text"] = snapshot_source
                structured_decisions.append(entry)

            if not structured_decisions:
                logger.error("AI response for %s contained no usable decision entries", account.name)
                return None

            logger.info(f"AI decisions for {account.name}: {structured_decisions}")
            return structured_decisions

        logger.error(f"Unexpected AI response format: {result}")
        return None
        
    except requests.RequestException as err:
        logger.error(f"AI API request failed: {err}")
        return None
    except json.JSONDecodeError as err:
        logger.error(f"Failed to parse AI response as JSON: {err}")
        # Try to log the content that failed to parse
        try:
            if 'text_content' in locals():
                logger.error(f"Content that failed to parse: {text_content[:500]}")
        except:
            pass
        return None
    except Exception as err:
        logger.error(f"Unexpected error calling AI: {err}", exc_info=True)
        return None
