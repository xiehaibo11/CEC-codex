"""
AI Prompt Generation Service - Handles AI-powered trading prompt generation

Supports Function Calling for AI to query variables reference, validate prompts, and preview.
Aligned with ai_program_service.py architecture for consistency.
"""
import json
import logging
import time
from typing import Any, Dict, Generator, Optional

import requests
from sqlalchemy.orm import Session

from database.models import Account, AiPromptMessage
from services.ai_decision_service import (
    _extract_text_from_message,
    build_llm_payload,
    convert_messages_to_anthropic,
    extract_reasoning,
    strip_thinking_tags,
)
from services.ai_prompt_generation_core import (
    API_MAX_RETRIES,
    _get_retry_delay,
    _should_retry_api,
    extract_prompt_from_response,
)
from services.ai_prompt_generation_history import (
    get_conversation_history,
    get_conversation_messages,
)
from services.ai_prompt_generation_runtime import (
    build_api_request_context,
    prepare_prompt_generation_context,
    resolve_prompt_api_config,
)
from services.ai_prompt_generation_tools import (
    PROMPT_TOOLS,
    PROMPT_TOOLS_ANTHROPIC,
    execute_tool,
)
from services.ai_stream_service import format_sse_event

logger = logging.getLogger(__name__)


# ============================================================================
# Main SSE Generation Function
# ============================================================================

def generate_prompt_with_ai_stream(
    db: Session,
    account: Optional[Account] = None,
    user_message: str = "",
    conversation_id: Optional[int] = None,
    user_id: int = 1,
    prompt_id: Optional[int] = None,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Generator[str, None, None]:
    """
    Generate trading strategy prompt using AI with SSE streaming.

    Yields SSE events:
    - tool_round: {type: "tool_round", round: N, max: M}
    - tool_call: {type: "tool_call", name: "...", args: {...}}
    - tool_result: {type: "tool_result", name: "...", result: "..."}
    - content: {type: "content", content: "..."}
    - suggest_apply: {type: "suggest_apply", prompt_text: "...", summary: "..."}
    - done: {type: "done", conversation_id: N, message_id: N, prompt_result: "..."}
    - error: {type: "error", content: "..."}
    - retry: {type: "retry", attempt: N, max_retries: M}
    """
    start_time = time.time()
    request_id = f"prompt_gen_{int(start_time)}"

    api_config, account_name, config_error = resolve_prompt_api_config(account, llm_config)
    if config_error:
        yield format_sse_event("error", {"content": config_error})
        return

    logger.info(f"[AI Prompt Gen {request_id}] Starting: account={account_name}, "
                f"conversation_id={conversation_id}, user_message_length={len(user_message)}")

    try:
        runtime_context = prepare_prompt_generation_context(
            db,
            api_config,
            user_id,
            prompt_id,
            conversation_id,
            user_message,
            request_id,
        )
        conversation = runtime_context["conversation"]
        messages = runtime_context["messages"]

        api_format, endpoints, headers, request_error = build_api_request_context(api_config)
        if request_error:
            yield format_sse_event("error", {"content": request_error})
            return

        # Tool calling loop
        max_rounds = 10
        tool_round = 0
        tool_calls_log = []
        final_content = ""
        reasoning_snapshot = ""
        prompt_result = None
        suggest_apply_data = None

        # Create assistant message upfront with is_complete=False
        assistant_msg = AiPromptMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            is_complete=False
        )
        db.add(assistant_msg)
        db.flush()

        while tool_round < max_rounds:
            tool_round += 1
            is_last = tool_round == max_rounds

            yield format_sse_event("tool_round", {"round": tool_round, "max": max_rounds})

            # Use unified payload builder (see build_llm_payload in ai_decision_service)
            if api_format == 'anthropic':
                sys_prompt, anthropic_messages = convert_messages_to_anthropic(messages)
                tools_for_round = PROMPT_TOOLS_ANTHROPIC if not is_last else None
                payload = build_llm_payload(
                    model=api_config["model"],
                    messages=[{"role": "system", "content": sys_prompt}] + anthropic_messages,
                    api_format=api_format,
                    tools=tools_for_round,
                )
            else:
                tools_for_round = PROMPT_TOOLS if not is_last else None
                payload = build_llm_payload(
                    model=api_config["model"],
                    messages=messages,
                    api_format=api_format,
                    tools=tools_for_round,
                    tool_choice="auto" if not is_last else None,
                )

            # API call with retry logic
            response = None
            last_error = None
            last_status_code = None
            last_response_text = None  # Store full response text for error logging

            for retry_attempt in range(API_MAX_RETRIES):
                response = None
                # Don't reset last_error - preserve error from previous attempts

                for ep in endpoints:
                    try:
                        logger.info(f"[AI Prompt Gen {request_id}] Round {tool_round}, trying: {ep}")
                        response = requests.post(ep, json=payload, headers=headers, timeout=120)
                        last_status_code = response.status_code
                        last_response_text = response.text[:2000] if response.text else None

                        if response.status_code == 200:
                            break
                        else:
                            last_error = f"HTTP {response.status_code}"
                            logger.warning(f"[AI Prompt Gen {request_id}] Endpoint failed: {response.status_code} - {response.text[:500]}")

                    except requests.exceptions.Timeout as e:
                        last_error = f"Timeout after 120s: {str(e)}"
                        logger.warning(f"[AI Prompt Gen {request_id}] Timeout on {ep}: {e}")
                    except requests.exceptions.ConnectionError as e:
                        last_error = f"Connection error: {str(e)}"
                        logger.warning(f"[AI Prompt Gen {request_id}] Connection error on {ep}: {e}")
                    except Exception as e:
                        last_error = f"{type(e).__name__}: {str(e)}"
                        logger.warning(f"[AI Prompt Gen {request_id}] Error: {type(e).__name__}: {e}")

                if response and response.status_code == 200:
                    break

                if not _should_retry_api(last_status_code, last_error):
                    break

                if retry_attempt < API_MAX_RETRIES - 1:
                    delay = _get_retry_delay(retry_attempt)
                    logger.warning(f"[AI Prompt Gen {request_id}] Retrying in {delay:.1f}s")
                    yield format_sse_event("retry", {"attempt": retry_attempt + 2, "max_retries": API_MAX_RETRIES})
                    time.sleep(delay)

            if not response or response.status_code != 200:
                error_parts = []
                if last_error:
                    error_parts.append(f"error={last_error}")
                if last_status_code:
                    error_parts.append(f"status={last_status_code}")
                if last_response_text:
                    error_parts.append(f"response={last_response_text[:500]}")
                error_detail = "; ".join(error_parts) if error_parts else "No response from API"
                logger.error(f"[AI Prompt Gen {request_id}] API failed at round {tool_round}: {error_detail}")

                if tool_calls_log:
                    assistant_msg.content = final_content
                    assistant_msg.tool_calls_log = json.dumps(tool_calls_log)
                    assistant_msg.is_complete = False
                    assistant_msg.interrupt_reason = f"Round {tool_round}: {error_detail}"
                    db.commit()
                    yield format_sse_event("interrupted", {"message_id": assistant_msg.id, "error": error_detail})
                else:
                    db.delete(assistant_msg)
                    db.commit()
                    yield format_sse_event("error", {"content": f"API request failed: {error_detail}"})
                return

            resp_json = response.json()

            # Parse response based on API format
            if api_format == 'anthropic':
                content_blocks = resp_json.get("content", [])
                tool_uses = []
                content = ""
                reasoning_content = ""

                for block in content_blocks:
                    if block.get("type") == "text":
                        content += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_uses.append(block)
                    elif block.get("type") == "thinking":
                        t = block.get("thinking", "")
                        if t:
                            reasoning_content += t

                if reasoning_content:
                    reasoning_snapshot += f"\n[Round {tool_round}]\n{reasoning_content}"
                    yield format_sse_event("reasoning", {"content": reasoning_content[:500]})

                # Strip <thinking> text tags from content
                content, tag_thinking = strip_thinking_tags(content)
                if tag_thinking and not reasoning_content:
                    reasoning_content = tag_thinking
                    reasoning_snapshot += f"\n[Round {tool_round}]\n{tag_thinking}"

                if tool_uses:
                    # Process tool calls
                    messages.append({
                        "role": "assistant",
                        "content": content,
                        "tool_use_blocks": content_blocks
                    })

                    for tool_use in tool_uses:
                        tool_name = tool_use.get("name", "")
                        tool_id = tool_use.get("id", "")
                        tool_args = tool_use.get("input", {})

                        yield format_sse_event("tool_call", {"name": tool_name, "args": tool_args})

                        result = execute_tool(tool_name, tool_args, request_id, db, prompt_id)
                        tool_calls_log.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": result[:500] if len(result) > 500 else result
                        })

                        # Check for suggest_apply
                        if tool_name == "suggest_apply_prompt":
                            try:
                                suggest_apply_data = json.loads(result)
                                yield format_sse_event("suggest_apply", {"prompt_text": suggest_apply_data.get("prompt_text", ""), "summary": suggest_apply_data.get("summary", "")})
                            except Exception:
                                pass

                        yield format_sse_event("tool_result", {"name": tool_name, "result": result[:200] + "..." if len(result) > 200 else result})

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result
                        })

                    continue  # Next round

                # No tool calls - final response
                final_content = content
                break

            else:
                # OpenAI format
                choice = resp_json.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = _extract_text_from_message(message.get("content", ""))
                tool_calls = message.get("tool_calls", [])
                # DeepSeek Reasoner returns reasoning_content which MUST be included in next request
                # Unified fallback: also handles Qwen thinking field via extract_reasoning()
                reasoning_content = message.get("reasoning_content", "") or extract_reasoning(message)

                # Strip <thinking> text tags from content
                content, tag_thinking = strip_thinking_tags(content)
                if tag_thinking and not reasoning_content:
                    reasoning_content = tag_thinking

                if tool_calls:
                    # Process tool calls - MUST include reasoning_content for DeepSeek Reasoner
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls
                    }
                    if reasoning_content:
                        assistant_msg_dict["reasoning_content"] = reasoning_content
                        reasoning_snapshot += f"\n[Round {tool_round}]\n{reasoning_content}"
                        # Stream reasoning to frontend
                        yield format_sse_event("reasoning", {"content": reasoning_content[:500]})
                    messages.append(assistant_msg_dict)

                    for tc in tool_calls:
                        func = tc.get("function", {})
                        tool_name = func.get("name", "")
                        tool_id = tc.get("id", "")
                        try:
                            tool_args = json.loads(func.get("arguments", "{}"))
                        except Exception:
                            tool_args = {}

                        yield format_sse_event("tool_call", {"name": tool_name, "args": tool_args})

                        result = execute_tool(tool_name, tool_args, request_id, db, prompt_id)
                        tool_calls_log.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": result[:500] if len(result) > 500 else result
                        })

                        # Check for suggest_apply
                        if tool_name == "suggest_apply_prompt":
                            try:
                                suggest_apply_data = json.loads(result)
                                yield format_sse_event("suggest_apply", {"prompt_text": suggest_apply_data.get("prompt_text", ""), "summary": suggest_apply_data.get("summary", "")})
                            except Exception:
                                pass

                        yield format_sse_event("tool_result", {"name": tool_name, "result": result[:200] + "..." if len(result) > 200 else result})

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result
                        })

                    continue  # Next round

                # No tool calls - final response
                final_content = content
                break

        # Extract prompt from final content
        prompt_result = extract_prompt_from_response(final_content)

        # Update and save assistant message
        assistant_msg.content = final_content
        assistant_msg.prompt_result = prompt_result
        assistant_msg.tool_calls_log = json.dumps(tool_calls_log) if tool_calls_log else None
        assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
        assistant_msg.is_complete = True
        db.commit()

        # Send final content and done event
        yield format_sse_event("content", {"content": final_content})
        done_data = {
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "prompt_result": prompt_result,
            "tool_calls_log": tool_calls_log if tool_calls_log else None,
            "reasoning_snapshot": reasoning_snapshot if reasoning_snapshot else None,
            "compression_points": json.loads(conversation.compression_points) if conversation.compression_points else None,
        }
        yield format_sse_event("done", done_data)

        total_elapsed = time.time() - start_time
        logger.info(f"[AI Prompt Gen {request_id}] Completed in {total_elapsed:.2f}s")

    except Exception as e:
        logger.error(f"[AI Prompt Gen {request_id}] Unexpected error: {e}", exc_info=True)
        db.rollback()
        yield format_sse_event("error", {"content": f"Internal error: {type(e).__name__}"})


# ============================================================================
# Legacy Synchronous Function (for backward compatibility)
# ============================================================================

def generate_prompt_with_ai(
    db: Session,
    account: Account,
    user_message: str,
    conversation_id: Optional[int] = None,
    user_id: int = 1,
    prompt_id: Optional[int] = None,
) -> Dict:
    """
    Legacy synchronous version - wraps the streaming version.
    Kept for backward compatibility with existing code.
    """
    result = {
        "success": False,
        "error": "Unknown error"
    }

    try:
        for event in generate_prompt_with_ai_stream(db, account, user_message, conversation_id, user_id, prompt_id):
            if event.startswith("data: "):
                data = json.loads(event[6:].strip())
                event_type = data.get("type")

                if event_type == "done":
                    result = {
                        "success": True,
                        "conversation_id": data.get("conversation_id"),
                        "message_id": data.get("message_id"),
                        "content": "",  # Will be set from content event
                        "prompt_result": data.get("prompt_result"),
                    }
                elif event_type == "content":
                    result["content"] = data.get("content", "")
                elif event_type == "error":
                    result = {
                        "success": False,
                        "error": data.get("content", "Unknown error")
                    }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }

    return result
