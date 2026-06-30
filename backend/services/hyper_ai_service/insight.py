"""One-shot Hyper AI Insight analysis.

A single streamed LLM call (no chat history, memory, or tools) that returns a
structured market-intelligence JSON object for a selected symbol/event.
"""
import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional

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

from services.hyper_ai_service.llm_config import get_llm_config
from services.hyper_ai_service.retry import (
    API_MAX_RETRIES,
    _should_retry_api,
    _get_retry_delay,
)

logger = logging.getLogger(__name__)


def _build_insight_messages(
    lang: str,
    context: Dict[str, Any],
    selected_event: Optional[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Build the one-shot Insight prompt without chat history, memory, or tools."""
    use_zh = (lang or "").startswith("zh")
    language_instruction = (
        "以中文回复。\n"
        "所有自然语言字段必须使用简体中文，包括 market_emotion、headline、summary、key_drivers.text、risks、explanation_markdown、next_cycle_period、confidence_basis、similar_pattern。\n"
        "即使输入数据或字段名是英文，输出内容也必须是中文，不能夹杂英文句子。\n"
    ) if use_zh else (
        "Respond in English.\n"
        "All natural-language fields must be written in English.\n"
    )

    system_prompt = (
        "You are Hyper AI inside CEC-codex.\n"
        f"{language_instruction}"
        "You analyze market intelligence for a retail crypto trader.\n"
        "Use only the provided context.\n"
        "Do not use external tools.\n"
        "Return exactly one JSON object and nothing else.\n"
        "Do not use markdown fences.\n"
        "Think in four layers before producing the JSON: technical structure, fund-flow behavior, news/event sentiment, and the conflicts between them.\n"
        "The final directional call must be grounded in those layers instead of giving a free-floating opinion.\n"
        "Use this exact schema:\n"
        "{\n"
        '  "sentiment": "bullish|bearish|mixed",\n'
        '  "probability": 0-100 integer,\n'
        '  "market_emotion": "short phrase",\n'
        '  "headline": "one sentence conclusion",\n'
        '  "summary": "2-3 sentence plain-language explanation",\n'
        '  "sentiment_breakdown": {\n'
        '    "technical": 0-100 integer,\n'
        '    "flow": 0-100 integer,\n'
        '    "news": 0-100 integer\n'
        '  },\n'
        '  "next_cycle_period": "the next period matching the current chart interval",\n'
        '  "next_cycle_target_price": number|null,\n'
        '  "next_cycle_range_low": number|null,\n'
        '  "next_cycle_range_high": number|null,\n'
        '  "technical_levels": [\n'
        '    {"price": number, "type": "support|resistance", "label": "short phrase"}\n'
        '  ],\n'
        '  "key_drivers": [\n'
        '    {"text": "driver 1", "impact": "high|medium|low", "tone": "bullish|bearish|mixed"}\n'
        '  ],\n'
        '  "risks": ["risk 1", "risk 2"],\n'
        '  "confidence_basis": "one sentence explaining why the confidence level is justified",\n'
        '  "similar_pattern": "short description of the nearest comparable market setup from recent behavior",\n'
        '  "explanation_markdown": "short markdown explanation with evidence bullets"\n'
        "}\n"
        "The probability must reflect directional confidence for the next cycle and should be justified by the breakdown scores, not guessed in isolation.\n"
        "The next-cycle target and range must be your forecast for the next period, even if uncertain.\n"
        "Use sentiment_breakdown to score each dimension independently: technical is based on kline structure, momentum, and nearby support/resistance; flow is based on large-order direction, OI change, and funding behavior; news is based on recent event tone, clustering, and relevance.\n"
        "Use technical_levels to identify the most relevant nearby support and resistance levels from the provided chart context.\n"
        "Use key_drivers to rank the most important catalysts. Impact must distinguish primary versus secondary drivers.\n"
        "Use confidence_basis to state what specifically makes the confidence believable.\n"
        "Use similar_pattern to describe the closest recent setup or regime match visible in the provided data. If there is no credible analogue, say that clearly.\n"
        'If evidence is mixed, set sentiment to "mixed" and explain the conflict clearly.\n'
        "The context includes kline behavior, all relevant symbol news events, and selected exchange fund-flow behavior."
    )

    user_payload = {
        "selected_event": selected_event,
        "context": context,
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def stream_insight_response(
    db: Session,
    context: Dict[str, Any],
    selected_event: Optional[Dict[str, Any]] = None,
    lang: str = "en",
) -> Generator[str, None, None]:
    """Stream a one-shot Insight analysis without conversation persistence."""
    llm_config = get_llm_config(db)
    if not llm_config.get("configured"):
        yield format_sse_event("error", {"message": "LLM not configured"})
        return

    base_url = llm_config["base_url"]
    model = llm_config["model"]
    api_key = llm_config["api_key"]
    api_format = llm_config.get("api_format", "openai")

    endpoints = build_chat_completion_endpoints(base_url, model)
    if not endpoints:
        yield format_sse_event("error", {"message": "Invalid API endpoint"})
        return

    headers = build_llm_headers(api_format, api_key, base_url)
    messages = _build_insight_messages(lang or "en", context, selected_event)
    body = build_llm_payload(
        model=model,
        messages=messages,
        api_format=api_format,
        stream=True,
        temperature=0.2,
    )

    response = None
    last_error = None
    last_status_code = None
    last_response_text = None

    for attempt in range(API_MAX_RETRIES):
        for endpoint in endpoints:
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=body,
                    stream=True,
                    timeout=180,
                )
                last_status_code = response.status_code
                last_response_text = response.text[:2000] if response.text else None
                if response.status_code == 200:
                    break
                last_error = f"HTTP {response.status_code}"
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout: {str(e)}"
            except requests.exceptions.RequestException as e:
                last_error = str(e)

        if response and response.status_code == 200:
            break

        if not _should_retry_api(last_status_code, last_error):
            break

        if attempt < API_MAX_RETRIES - 1:
            yield format_sse_event("retry", {
                "attempt": attempt + 2,
                "max_retries": API_MAX_RETRIES
            })
            time.sleep(_get_retry_delay(attempt))

    if not response or response.status_code != 200:
        error_parts = []
        if last_error:
            error_parts.append(f"error={last_error}")
        if last_status_code:
            error_parts.append(f"status={last_status_code}")
        if last_response_text:
            error_parts.append(f"response={last_response_text[:500]}")
        error_detail = "; ".join(error_parts) if error_parts else "No response from API"
        yield format_sse_event("error", {"message": error_detail})
        return

    content_parts: List[str] = []
    reasoning_parts: List[str] = []

    try:
        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode("utf-8")
            if not line_str.startswith("data: "):
                continue

            data_str = line_str[6:]
            if data_str == "[DONE]":
                break

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if api_format == "anthropic":
                event_type = data.get("type")
                if event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            content_parts.append(text)
                            yield format_sse_event("content", {"text": text})
                elif event_type == "content_block_start":
                    content_block = data.get("content_block", {})
                    if content_block.get("type") == "thinking":
                        thinking = content_block.get("thinking", "")
                        if thinking:
                            reasoning_parts.append(thinking)
                            yield format_sse_event("reasoning", {"content": thinking})
            else:
                choices = data.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                text = delta.get("content", "")
                if text:
                    content_parts.append(text)
                    yield format_sse_event("content", {"text": text})

                reasoning = delta.get("reasoning_content", "")
                if reasoning:
                    reasoning_parts.append(reasoning)
                    yield format_sse_event("reasoning", {"content": reasoning})

        full_content = "".join(content_parts)
        full_reasoning = "".join(reasoning_parts) if reasoning_parts else None

        full_content, tag_thinking = strip_thinking_tags(full_content)
        if tag_thinking:
            full_reasoning = (full_reasoning + "\n\n" + tag_thinking).strip() if full_reasoning else tag_thinking

        yield format_sse_event("done", {
            "content": full_content.strip(),
            "reasoning": full_reasoning,
        })
    except Exception as e:
        yield format_sse_event("error", {"message": str(e)})


def start_insight_task(
    db: Session,
    context: Dict[str, Any],
    selected_event: Optional[Dict[str, Any]] = None,
    lang: Optional[str] = None,
) -> str:
    """Start a one-shot Insight analysis task without chat conversation persistence."""
    task_id = generate_task_id("insight")
    manager = get_buffer_manager()
    manager.create_task(task_id, None)

    effective_lang = lang or "en"

    def generator_func():
        from database.connection import SessionLocal
        task_db = SessionLocal()
        try:
            yield from stream_insight_response(
                task_db,
                context=context,
                selected_event=selected_event,
                lang=effective_lang,
            )
        finally:
            task_db.close()

    run_ai_task_in_background(task_id, generator_func)
    return task_id
