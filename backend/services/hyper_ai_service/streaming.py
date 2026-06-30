"""Hyper AI streaming tool-use loop.

`stream_chat_response` is the central orchestrator: it builds messages, calls
the LLM with retries, processes tool calls through the harness, and persists
the assistant message. `start_chat_task` runs that generator in a background
StreamBuffer task. See the docstrings below for the buffer/polling contract.
"""
import json
import logging
import time
from typing import Generator, Optional

import requests
from sqlalchemy.orm import Session

from database.models import (
    HyperAiProfile,
    HyperAiConversation,
    HyperAiMessage,
)
from services.ai_decision_service import (
    build_chat_completion_endpoints,
    build_llm_payload,
    build_llm_headers,
    extract_reasoning,
    convert_tools_to_anthropic,
    convert_messages_to_anthropic,
    strip_thinking_tags,
)
from services.ai_stream_service import (
    get_buffer_manager,
    generate_task_id,
    run_ai_task_in_background,
    format_sse_event,
)
from services.hyper_ai_harness import ToolFailureTracker

from services.hyper_ai_service.context import build_messages_for_api
from services.hyper_ai_service.conversations import save_message
from services.hyper_ai_service.llm_config import get_llm_config
from services.hyper_ai_service.retry import (
    API_MAX_RETRIES,
    _should_retry_api,
    _get_retry_delay,
)
from services.hyper_ai_service.tool_execution import _execute_harnessed_tool_call

logger = logging.getLogger(__name__)

# Maximum tool call iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 100


def stream_chat_response(
    db: Session,
    conversation_id: int,
    user_message: str,
    task_id: Optional[str] = None
) -> Generator[str, None, None]:
    """
    Stream chat response from LLM with tool calling support.

    ARCHITECTURE NOTE: This is a generator that yields SSE-formatted strings.
    It does NOT stream directly to the frontend. Instead:
    - start_chat_task() wraps this generator and passes it to run_ai_task_in_background()
    - run_ai_task_in_background() runs this in a background thread, parsing each yielded
      SSE event and storing it in StreamBufferManager (in-memory buffer)
    - Frontend polls /api/ai-stream/{task_id}?offset=N to pull events from the buffer
    - This means ANY event yielded here automatically reaches the frontend via polling,
      and survives frontend disconnects (buffer has 15-min expiry)

    For sub-agent calls (call_*_ai), the tool execution returns a generator instead of
    a string. This generator yields subagent_progress events (forwarded to frontend)
    and finally yields the result string for the main LLM to continue reasoning.
    """
    # Get LLM config
    llm_config = get_llm_config(db)
    if not llm_config.get("configured"):
        yield format_sse_event("error", {
            "message": "LLM not configured. Please complete onboarding first."
        })
        return

    # Save user message
    save_message(db, conversation_id, "user", user_message)

    # Build messages (with automatic compression) and get tools
    messages, tools, command_skill = build_messages_for_api(db, conversation_id, user_message, llm_config)

    # Emit skill_loaded event if /command mode was used
    if command_skill:
        yield format_sse_event("skill_loaded", {"skill_name": command_skill})

    # Prepare API call
    base_url = llm_config["base_url"]
    model = llm_config["model"]
    api_key = llm_config["api_key"]
    api_format = llm_config.get("api_format", "openai")

    # Build endpoints
    endpoints = build_chat_completion_endpoints(base_url, model)
    if not endpoints:
        yield format_sse_event("error", {"message": "Invalid API endpoint"})
        return

    # Use unified headers builder (see build_llm_headers in ai_decision_service)
    headers = build_llm_headers(api_format, api_key, base_url)

    # Create assistant message upfront with is_complete=False for interrupt recovery
    assistant_msg = HyperAiMessage(
        conversation_id=conversation_id,
        role="assistant",
        content="",
        is_complete=False
    )
    db.add(assistant_msg)
    db.flush()

    # Tool call loop variables
    tool_calls_log = []
    reasoning_snapshot = ""
    final_content = ""
    iteration = 0
    failure_tracker = ToolFailureTracker()

    try:
        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1
            is_last_round = (iteration == MAX_TOOL_ITERATIONS)

            # On last round, inject a system message forcing the AI to summarize
            if is_last_round:
                messages.append({
                    "role": "user",
                    "content": "[SYSTEM] You have reached the maximum tool call limit. You MUST now provide your final response to the user. Summarize all findings from your tool calls and answer the user's question. Do NOT attempt any more tool calls."
                })

            # Use unified payload builder (see build_llm_payload in ai_decision_service)
            if api_format == "anthropic":
                sys_prompt, anthropic_messages = convert_messages_to_anthropic(messages)
                anthropic_tools = convert_tools_to_anthropic(tools) if tools and not is_last_round else None
                body = build_llm_payload(
                    model=model,
                    messages=[{"role": "system", "content": sys_prompt}] + anthropic_messages,
                    api_format=api_format,
                    tools=anthropic_tools,
                )
            else:
                body = build_llm_payload(
                    model=model,
                    messages=messages,
                    api_format=api_format,
                    tools=tools if tools and not is_last_round else None,
                    tool_choice="auto" if tools and not is_last_round else None,
                )

            # Make API call with retry
            response = None
            last_error = None
            last_status_code = None
            last_response_text = None

            for attempt in range(API_MAX_RETRIES):
                for endpoint in endpoints:
                    try:
                        response = requests.post(
                            endpoint, headers=headers, json=body,
                            timeout=180  # Longer timeout for reasoning models
                        )
                        last_status_code = response.status_code
                        last_response_text = response.text[:2000] if response.text else None

                        if response.status_code == 200:
                            break
                        else:
                            last_error = f"HTTP {response.status_code}"
                            logger.warning(f"[HyperAI] Endpoint failed: {response.status_code} - {response.text[:500]}")
                    except requests.exceptions.Timeout as e:
                        last_error = f"Timeout: {str(e)}"
                        logger.warning(f"[HyperAI] Endpoint timeout: {e}")
                    except requests.exceptions.RequestException as e:
                        last_error = str(e)
                        logger.warning(f"[HyperAI] Request error: {e}")

                if response and response.status_code == 200:
                    break

                # Check if should retry
                if not _should_retry_api(last_status_code, last_error):
                    break

                if attempt < API_MAX_RETRIES - 1:
                    delay = _get_retry_delay(attempt)
                    yield format_sse_event("retry", {
                        "attempt": attempt + 2,
                        "max_retries": API_MAX_RETRIES
                    })
                    time.sleep(delay)

            # Check for failure
            if not response or response.status_code != 200:
                error_parts = []
                if last_error:
                    error_parts.append(f"error={last_error}")
                if last_status_code:
                    error_parts.append(f"status={last_status_code}")
                if last_response_text:
                    error_parts.append(f"response={last_response_text[:500]}")
                error_detail = "; ".join(error_parts) if error_parts else "No response from API"
                logger.error(f"[HyperAI] API failed at round {iteration}: {error_detail}")

                if tool_calls_log:
                    assistant_msg.content = f"[Interrupted at round {iteration}] {error_detail}"
                    assistant_msg.tool_calls_log = json.dumps(tool_calls_log)
                    assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
                    assistant_msg.interrupt_reason = f"Round {iteration}: {error_detail}"
                    db.commit()
                    yield format_sse_event("interrupted", {
                        "message_id": assistant_msg.id,
                        "round": iteration,
                        "error": error_detail,
                        "conversation_id": conversation_id
                    })
                else:
                    db.delete(assistant_msg)
                    db.commit()
                    yield format_sse_event("error", {"message": error_detail})
                return

            # Parse response
            try:
                resp_json = response.json()
            except Exception as e:
                logger.error(f"[HyperAI] Failed to parse response: {e}")
                yield format_sse_event("error", {"message": f"Failed to parse response: {e}"})
                return

            # Extract message based on API format
            if api_format == "anthropic":
                # Anthropic format
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
                api_tool_calls = tool_uses
            else:
                # OpenAI format
                message = resp_json["choices"][0]["message"]
                api_tool_calls = message.get("tool_calls", [])
                reasoning_content = message.get("reasoning_content", "") or extract_reasoning(message)
                content = message.get("content", "")

            # Strip <thinking> text tags from content (some proxies embed them)
            content, tag_thinking = strip_thinking_tags(content)
            if tag_thinking and not reasoning_content:
                reasoning_content = tag_thinking

            # Send reasoning content if present
            if reasoning_content:
                yield format_sse_event("reasoning", {"content": reasoning_content})
                reasoning_snapshot += f"\n[Round {iteration}]\n{reasoning_content}"

            # Send content if present
            if content:
                yield format_sse_event("content", {"text": content})

            if api_tool_calls:
                # Process tool calls - build assistant message with reasoning_content for DeepSeek
                if api_format == "anthropic":
                    # Anthropic format - store tool_use_blocks for convert_messages_to_anthropic
                    messages.append({
                        "role": "assistant",
                        "content": content or "",
                        "tool_use_blocks": content_blocks
                    })
                    for tu in api_tool_calls:
                        fn_name = tu.get("name", "")
                        fn_args = tu.get("input", {})
                        tool_use_id = tu.get("id", "")
                        if fn_args == "":
                            fn_args = {}

                        yield format_sse_event("tool_call", {"name": fn_name, "args": fn_args})
                        tool_result = yield from _execute_harnessed_tool_call(
                            db=db,
                            assistant_msg=assistant_msg,
                            task_id=task_id,
                            fn_name=fn_name,
                            fn_args=fn_args,
                            failure_tracker=failure_tracker,
                            llm_config=llm_config,
                        )

                        # Emit skill_loaded event so frontend can show skill status
                        if fn_name == "load_skill":
                            yield format_sse_event("skill_loaded", {
                                "skill_name": fn_args.get("skill_name", "")
                            })

                        tool_calls_log.append({
                            "tool": fn_name,
                            "args": fn_args,
                            # Tool results are user-visible in the frontend stream/log.
                            # Do not include internal URLs, auth headers, API keys, or raw upstream errors here.
                            # Keep full result for save/create tools (needed for entity cards)
                            # Truncate others to avoid bloating tool_calls_log
                            "result": tool_result if fn_name in ('save_prompt', 'save_program', 'save_signal_pool', 'create_ai_trader') else (tool_result[:500] if len(tool_result) > 500 else tool_result)
                        })
                        yield format_sse_event("tool_result", {
                            "name": fn_name,
                            "result": tool_result[:200] if len(tool_result) > 200 else tool_result
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id,
                            "content": tool_result
                        })
                else:
                    # OpenAI format - MUST include reasoning_content for DeepSeek Reasoner
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": content or "",
                        "tool_calls": api_tool_calls
                    }
                    if reasoning_content:
                        assistant_msg_dict["reasoning_content"] = reasoning_content
                    messages.append(assistant_msg_dict)

                    for tc in api_tool_calls:
                        fn_name = tc["function"]["name"]
                        try:
                            fn_args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            fn_args = {}

                        yield format_sse_event("tool_call", {"name": fn_name, "args": fn_args})
                        tool_result = yield from _execute_harnessed_tool_call(
                            db=db,
                            assistant_msg=assistant_msg,
                            task_id=task_id,
                            fn_name=fn_name,
                            fn_args=fn_args,
                            failure_tracker=failure_tracker,
                            llm_config=llm_config,
                        )

                        # Emit skill_loaded event so frontend can show skill status
                        if fn_name == "load_skill":
                            yield format_sse_event("skill_loaded", {
                                "skill_name": fn_args.get("skill_name", "")
                            })

                        tool_calls_log.append({
                            "tool": fn_name,
                            "args": fn_args,
                            # Tool results are user-visible in the frontend stream/log.
                            # Do not include internal URLs, auth headers, API keys, or raw upstream errors here.
                            # Keep full result for save/create tools (needed for entity cards)
                            # Truncate others to avoid bloating tool_calls_log
                            "result": tool_result if fn_name in ('save_prompt', 'save_program', 'save_signal_pool', 'create_ai_trader') else (tool_result[:500] if len(tool_result) > 500 else tool_result)
                        })
                        yield format_sse_event("tool_result", {
                            "name": fn_name,
                            "result": tool_result[:200] if len(tool_result) > 200 else tool_result
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_result
                        })

                # Save progress after each round (for retry support)
                if tool_calls_log:
                    assistant_msg.content = f"[Processing round {iteration}...]"
                    assistant_msg.tool_calls_log = json.dumps(tool_calls_log)
                    assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
                    db.commit()
            else:
                # No tool calls - final response
                final_content = content or ""
                break

        # Handle case where final_content is empty (AI ended with tool calls)
        if not final_content:
            if api_format != "anthropic" and 'message' in dir() and message:
                last_content = message.get("content", "")
                if last_content:
                    final_content = last_content
            if not final_content:
                final_content = "Processing completed."

        # Update assistant message and mark as complete
        assistant_msg.content = final_content
        assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
        assistant_msg.tool_calls_log = json.dumps(tool_calls_log) if tool_calls_log else None
        assistant_msg.is_complete = True

        # Update conversation message count for assistant message
        conv = db.query(HyperAiConversation).filter(
            HyperAiConversation.id == conversation_id
        ).first()
        if conv:
            conv.message_count = (conv.message_count or 0) + 1
        db.commit()

        # Calculate fresh token usage and compression points for frontend
        done_data = {
            "conversation_id": conversation_id,
            "content": final_content,
            "tool_calls_count": len(tool_calls_log),
            "tool_calls_log": tool_calls_log if tool_calls_log else None,
            "reasoning_snapshot": reasoning_snapshot if reasoning_snapshot else None,
        }
        try:
            from services.ai_context_compression_service import (
                calculate_token_usage, restore_tool_calls_to_messages,
                get_last_compression_point
            )
            import json as json_mod
            profile = db.query(HyperAiProfile).first()
            if profile and profile.llm_model and conv:
                llm_cfg = get_llm_config(db)
                af = llm_cfg.get("api_format", "openai")
                cp = get_last_compression_point(conv)
                cp_mid = cp.get("message_id", 0) if cp else 0
                h_orm = db.query(HyperAiMessage).filter(
                    HyperAiMessage.conversation_id == conversation_id,
                    HyperAiMessage.id > cp_mid
                ).order_by(HyperAiMessage.created_at).all()
                md = [
                    {
                        "role": m.role,
                        "content": m.content,
                        "tool_calls_log": m.tool_calls_log,
                        "reasoning_snapshot": m.reasoning_snapshot,
                    }
                    for m in h_orm
                ]
                ml = restore_tool_calls_to_messages(md, af, model=profile.llm_model or "")
                if cp and cp.get("summary"):
                    ml.insert(0, {"role": "system", "content": cp["summary"]})
                done_data["token_usage"] = calculate_token_usage(ml, profile.llm_model)
            if conv and conv.compression_points:
                done_data["compression_points"] = json_mod.loads(conv.compression_points)
        except Exception as te:
            logger.warning(f"[HyperAI] Token calc in done event failed: {te}")

        yield format_sse_event("done", done_data)

    except Exception as e:
        logger.error(f"[HyperAI] Error: {e}", exc_info=True)
        if tool_calls_log:
            assistant_msg.content = f"[Error during processing] {str(e)}"
            assistant_msg.tool_calls_log = json.dumps(tool_calls_log)
            assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
            assistant_msg.interrupt_reason = f"Error: {str(e)}"
            db.commit()
            yield format_sse_event("interrupted", {
                "message_id": assistant_msg.id,
                "error": str(e),
                "conversation_id": conversation_id
            })
        else:
            db.delete(assistant_msg)
            db.commit()
            yield format_sse_event("error", {"message": str(e)})


def start_chat_task(
    db: Session,
    conversation_id: int,
    user_message: str,
    lang: str = None
) -> str:
    """Start a chat task in background and return task_id."""
    task_id = generate_task_id("hyper")
    manager = get_buffer_manager()
    manager.create_task(task_id, conversation_id)

    def generator_func():
        from database.connection import SessionLocal
        task_db = SessionLocal()
        try:
            yield from stream_chat_response(task_db, conversation_id, user_message, task_id=task_id)
        finally:
            task_db.close()

    run_ai_task_in_background(task_id, generator_func)
    return task_id
