"""Response parsing helpers for AI trading decisions."""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from services.ai_decision_service.llm_payload import _extract_text_from_message

logger = logging.getLogger(__name__)


def parse_streaming_response(response) -> Optional[Dict[str, Any]]:
    """Parse an OpenAI-compatible SSE stream into a response-like dict."""
    try:
        full_content = ""
        reasoning_content = ""
        chunk_count = 0

        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode("utf-8")
            if not line_str.startswith("data: "):
                continue

            json_str = line_str[6:]
            if json_str.strip() == "[DONE]":
                break

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as err:
                logger.warning("JSON decode error in streaming response: %s", err)
                continue

            chunk_count += 1
            if not data.get("choices"):
                continue

            delta = data["choices"][0].get("delta", {})
            full_content += delta.get("content") or ""
            reasoning_content += delta.get("reasoning_content") or ""

        result = {
            "choices": [{
                "message": {
                    "content": full_content,
                    "reasoning_content": reasoning_content,
                },
                "finish_reason": "stop",
            }]
        }

        logger.info(
            "Streaming response completed: %s chunks, content: %s chars, reasoning: %s chars",
            chunk_count,
            len(full_content),
            len(reasoning_content),
        )
        return result
    except Exception as err:
        logger.error("Failed to parse streaming response: %s", err)
        return None


def extract_api_reasoning_content(api_result: dict) -> str:
    """
    Extract reasoning content from a multi-vendor AI response.

    Supports OpenAI-compatible reasoning fields, Claude thinking blocks,
    Gemini thought parts, and common fallback field names. Any extraction
    failure returns an empty string so trading flow is not blocked.
    """
    try:
        reasoning_parts = []
        choices = api_result.get("choices")
        if not choices or not isinstance(choices, list):
            return ""

        choice_item = choices[0]
        if not isinstance(choice_item, dict):
            return ""

        msg = choice_item.get("message")
        if not isinstance(msg, dict):
            return ""

        for field_name in ("reasoning", "reasoning_content"):
            try:
                field_value = msg.get(field_name)
                if not field_value:
                    continue

                extracted = _extract_text_from_message(field_value)
                if extracted and extracted.strip():
                    reasoning_parts.append(extracted.strip())
            except Exception:
                pass

        try:
            content_array = msg.get("content")
            if isinstance(content_array, list):
                for block in content_array:
                    if not isinstance(block, dict) or block.get("type") != "thinking":
                        continue

                    thinking_text = block.get("thinking")
                    if thinking_text and isinstance(thinking_text, str) and thinking_text.strip():
                        reasoning_parts.append(thinking_text.strip())
        except Exception:
            pass

        try:
            parts_array = msg.get("parts")
            if isinstance(parts_array, list):
                for part in parts_array:
                    if not isinstance(part, dict) or part.get("thought") is not True:
                        continue

                    thought_text = part.get("text")
                    if thought_text and isinstance(thought_text, str) and thought_text.strip():
                        reasoning_parts.append(thought_text.strip())
        except Exception:
            pass

        try:
            fallback_fields = (
                "chain_of_thought",
                "cot",
                "thinking",
                "thinking_log",
                "reasoning_log",
            )
            for field_name in fallback_fields:
                field_value = msg.get(field_name)
                if not field_value:
                    continue

                extracted = _extract_text_from_message(field_value)
                if extracted and extracted.strip():
                    reasoning_parts.append(extracted.strip())
                    break
        except Exception:
            pass

        if not reasoning_parts:
            return ""

        merged = "\n\n--- [Reasoning Section] ---\n\n".join(reasoning_parts)
        logger.debug("Reasoning content extracted: %s chars from API response", len(merged))
        return merged
    except Exception as err:
        logger.warning("Failed to extract reasoning content from API response: %s", err)
        return ""


def extract_response_text(result: Dict[str, Any]) -> Tuple[Optional[str], str, str]:
    """Return text content, reasoning text, and API reasoning from a response dict."""
    if "choices" not in result or len(result["choices"]) == 0:
        logger.error("Unexpected AI response format: %s", result)
        return None, "", ""

    choice = result["choices"][0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "")
    reasoning_text = _extract_text_from_message(message.get("reasoning"))
    api_reasoning_content = extract_api_reasoning_content(result)

    if finish_reason == "length":
        logger.warning("AI response was truncated due to token limit. Consider increasing max_tokens.")
        raw_content = message.get("reasoning") or message.get("content")
    else:
        raw_content = message.get("content")

    text_content = _extract_text_from_message(raw_content)
    if not text_content and reasoning_text:
        text_content = reasoning_text
    elif not text_content and api_reasoning_content:
        text_content = api_reasoning_content
        logger.info("Using reasoning_content as fallback for empty content (DeepSeek Reasoner)")

    if not text_content:
        logger.error("Empty content in AI response: %s", {k: v for k, v in result.items() if k != "usage"})
        return None, reasoning_text, api_reasoning_content

    return text_content, reasoning_text, api_reasoning_content


def parse_decision_payload(text_content: str) -> Optional[Tuple[Any, str, str]]:
    """Parse or recover an AI decision payload from raw model text."""
    raw_decision_text = text_content.strip()
    cleaned_content = raw_decision_text
    if "```json" in cleaned_content:
        cleaned_content = cleaned_content.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned_content:
        cleaned_content = cleaned_content.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(cleaned_content), cleaned_content, raw_decision_text
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
        logger.info("Successfully parsed AI decision after cleanup")
        return decision, cleaned, raw_decision_text
    except json.JSONDecodeError:
        logger.error("JSON parsing failed after cleanup, attempting manual extraction")
        logger.error("Original AI response: %s...", text_content[:1000])
        logger.error("Cleaned content: %s...", cleaned[:1000])

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
        return decision, json.dumps(decision), raw_decision_text

    logger.error("Unable to extract required fields from AI response")
    logger.error(
        "Regex match results - operation: %s, symbol: %s, portion: %s, reason: %s...",
        operation_match.group(1) if operation_match else None,
        symbol_match.group(1) if symbol_match else None,
        portion_match.group(1) if portion_match else None,
        reason_match.group(1)[:100] if reason_match else None,
    )
    return None


def normalize_decision_entries(decision: Any) -> Optional[List[Dict[str, Any]]]:
    """Normalize parsed AI output into a list of decision dictionaries."""
    if isinstance(decision, dict) and isinstance(decision.get("decisions"), list):
        return decision.get("decisions") or []
    if isinstance(decision, list):
        return decision
    if isinstance(decision, dict):
        return [decision]

    logger.error("AI response has unsupported structure: %s", type(decision))
    return None


def build_structured_decisions(
    decision_entries: List[Dict[str, Any]],
    account_name: str,
    prompt: str,
    api_reasoning_content: str,
    reasoning_text: str,
    snapshot_source: str,
) -> List[Dict[str, Any]]:
    """Attach prompt/reasoning snapshots and skip unusable decision entries."""
    structured_decisions: List[Dict[str, Any]] = []

    for idx, raw_entry in enumerate(decision_entries):
        if not isinstance(raw_entry, dict):
            logger.warning(
                "Skipping decision entry %s for account %s because it is %s instead of dict",
                idx,
                account_name,
                type(raw_entry),
            )
            continue

        entry = dict(raw_entry)
        strategy_details = entry.get("trading_strategy")
        entry["_prompt_snapshot"] = prompt

        if api_reasoning_content:
            base_strategy = strategy_details if isinstance(strategy_details, str) and strategy_details.strip() else ""
            entry["_reasoning_snapshot"] = (
                f"{base_strategy}\n\n{api_reasoning_content}" if base_strategy else api_reasoning_content
            )
        elif isinstance(strategy_details, str) and strategy_details.strip():
            entry["_reasoning_snapshot"] = strategy_details.strip()
        else:
            entry["_reasoning_snapshot"] = reasoning_text or ""

        entry["_raw_decision_text"] = snapshot_source
        structured_decisions.append(entry)

    return structured_decisions
