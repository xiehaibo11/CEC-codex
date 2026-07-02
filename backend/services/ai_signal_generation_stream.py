"""Streaming AI signal generation."""
import json
import logging
import time
from typing import Any, Dict, Optional

import requests
from sqlalchemy.orm import Session

from database.models import AiSignalConversation, AiSignalMessage, Account
from services.ai_decision_service import (
    build_chat_completion_endpoints,
    detect_api_format,
    _extract_text_from_message,
    build_llm_payload,
    build_llm_headers,
    extract_reasoning,
    convert_tools_to_anthropic,
    convert_messages_to_anthropic,
    strip_thinking_tags,
)
from services.ai_signal_generation_config import SIGNAL_SYSTEM_PROMPT, SIGNAL_TOOLS
from services.ai_signal_generation_parser import extract_signal_configs
from services.ai_signal_generation_tool_prediction import _execute_tool, _sse_event
from services.system_logger import system_logger

logger = logging.getLogger(__name__)

def generate_signal_with_ai_stream(
    db: Session,
    account_id: Optional[int] = None,
    user_message: str = "",
    conversation_id: Optional[int] = None,
    user_id: int = 1,
    llm_config: Optional[Dict[str, Any]] = None
):
    """
    Generate signal configuration using AI with SSE streaming.
    Yields SSE events for real-time progress updates.

    Event types:
    - status: Progress status message
    - tool_call: Tool being called with arguments
    - tool_result: Result from tool execution
    - content: AI response content chunk
    - signal_config: Parsed signal configuration
    - done: Completion with final result
    - error: Error occurred
    """
    start_time = time.time()
    request_id = f"signal_gen_{int(start_time)}"

    logger.info(f"[AI Signal Gen Stream {request_id}] Starting")
    yield _sse_event("status", {"message": "Initializing AI signal generation..."})

    try:
        # Get LLM config: either from llm_config param or from account_id
        if llm_config:
            # Use provided llm_config (e.g., from Hyper AI sub-agent call)
            api_config = {
                "base_url": llm_config.get("base_url"),
                "api_key": llm_config.get("api_key"),
                "model": llm_config.get("model"),
                "api_format": llm_config.get("api_format", "openai")
            }
            model_name = llm_config.get("model", "unknown")
            account = None
        else:
            # Original logic: get from AI account
            account = db.query(Account).filter(
                Account.id == account_id,
                Account.account_type == "AI",
                Account.is_deleted != True
            ).first()

            if not account:
                yield _sse_event("error", {"message": "AI account not found"})
                return

            api_config = {
                "base_url": account.base_url,
                "api_key": account.api_key,
                "model": account.model,
                "api_format": detect_api_format(account.base_url)[1] or "openai"
            }
            model_name = account.model

        yield _sse_event("status", {"message": f"Using model: {model_name}"})

        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = db.query(AiSignalConversation).filter(
                AiSignalConversation.id == conversation_id,
                AiSignalConversation.user_id == user_id
            ).first()

        is_new_conversation = False
        if not conversation:
            title = user_message[:50] + "..." if len(user_message) > 50 else user_message
            conversation = AiSignalConversation(user_id=user_id, title=title)
            db.add(conversation)
            db.flush()
            is_new_conversation = True

        # Notify frontend of conversation ID immediately (so it can recover from interruptions)
        if is_new_conversation:
            yield _sse_event("conversation_created", {"conversation_id": conversation.id})

        # Save user message
        user_msg = AiSignalMessage(
            conversation_id=conversation.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        db.flush()

        # Build message history with compression support
        from services.ai_context_compression_service import (
            compress_messages, update_compression_points,
            restore_tool_calls_to_messages,
            get_last_compression_point, filter_messages_by_compression,
        )

        messages = [{"role": "system", "content": SIGNAL_SYSTEM_PROMPT}]

        # Check compression points - inject summary for compressed messages
        cp = get_last_compression_point(conversation)
        if cp and cp.get("summary"):
            messages.append({
                "role": "system",
                "content": f"[Previous conversation summary]\n{cp['summary']}"
            })

        # Load history, filter by compression point
        history_messages = db.query(AiSignalMessage).filter(
            AiSignalMessage.conversation_id == conversation.id,
            AiSignalMessage.id != user_msg.id
        ).order_by(AiSignalMessage.created_at).limit(100).all()

        history_messages = filter_messages_by_compression(history_messages, cp)

        last_message_id = history_messages[-1].id if history_messages else None

        # Restore tool_calls into proper LLM message format
        history_dicts = [
            {
                "role": m.role,
                "content": m.content,
                "tool_calls_log": m.tool_calls_log,
                "reasoning_snapshot": m.reasoning_snapshot,
            }
            for m in history_messages
        ]
        restored = restore_tool_calls_to_messages(history_dicts, api_config.get("api_format", "openai"), model=api_config.get("model", ""))
        messages.extend(restored)
        messages.append({"role": "user", "content": user_message})

        # Apply compression if needed (api_config already set above)
        comp_result = compress_messages(messages, api_config, db=db)
        messages = comp_result["messages"]

        # Update compression_points if compression occurred
        if comp_result["compressed"] and comp_result["summary"] and last_message_id:
            update_compression_points(
                conversation, last_message_id,
                comp_result["summary"], comp_result["compressed_at"], db
            )

        # Build endpoints and headers
        api_format = api_config.get("api_format", "openai")
        if api_format == 'anthropic':
            ep, _ = detect_api_format(api_config["base_url"])
            endpoints = [ep] if ep else []
        else:
            endpoints = build_chat_completion_endpoints(api_config["base_url"], api_config["model"])
        if not endpoints:
            yield _sse_event("error", {"message": "Invalid base_url configuration"})
            return

        # Use unified headers builder (see build_llm_headers in ai_decision_service)
        headers = build_llm_headers(api_format, api_config["api_key"], api_config["base_url"])

        yield _sse_event("status", {"message": "Analyzing your request..."})

        # Function Calling loop (max 30 rounds)
        max_tool_rounds = 30
        tool_round = 0
        assistant_content = None
        # Accumulate tool calls and reasoning for storage (aligned with other AI assistants)
        tool_calls_log = []
        reasoning_snapshot_parts = []

        while tool_round < max_tool_rounds:
            tool_round += 1
            is_last_round = (tool_round == max_tool_rounds)

            yield _sse_event("tool_round", {
                "round": tool_round,
                "max_rounds": max_tool_rounds
            })

            if is_last_round:
                messages.append({
                    "role": "user",
                    "content": "Output the final signal configuration now. Include the ```signal-config``` block."
                })

            # Use unified payload builder (see build_llm_payload in ai_decision_service)
            if api_format == 'anthropic':
                sys_prompt, anthropic_messages = convert_messages_to_anthropic(messages)
                tools_for_round = convert_tools_to_anthropic(SIGNAL_TOOLS) if not is_last_round else None
                request_payload = build_llm_payload(
                    model=api_config["model"],
                    messages=[{"role": "system", "content": sys_prompt}] + anthropic_messages,
                    api_format=api_format,
                    tools=tools_for_round,
                )
            else:
                request_payload = build_llm_payload(
                    model=api_config["model"],
                    messages=messages,
                    api_format=api_format,
                    tools=SIGNAL_TOOLS if not is_last_round else None,
                    tool_choice="auto" if not is_last_round else None,
                )

            # Call API
            response = None
            last_error = None
            last_status_code = None
            last_response_text = None

            for endpoint in endpoints:
                try:
                    response = requests.post(endpoint, json=request_payload, headers=headers, timeout=120)
                    last_status_code = response.status_code
                    last_response_text = response.text[:2000] if response.text else None
                    if response.status_code == 200:
                        break
                    else:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(f"[AI Signal Gen Stream {request_id}] Endpoint failed: {response.status_code} - {response.text[:500]}")
                except requests.exceptions.Timeout as e:
                    last_error = f"Timeout after 120s: {str(e)}"
                    logger.warning(f"[AI Signal Gen Stream {request_id}] Endpoint timeout: {e}")
                except requests.exceptions.ConnectionError as e:
                    last_error = f"Connection error: {str(e)}"
                    logger.warning(f"[AI Signal Gen Stream {request_id}] Connection error: {e}")
                except Exception as e:
                    last_error = f"{type(e).__name__}: {str(e)}"
                    logger.warning(f"[AI Signal Gen Stream {request_id}] Endpoint error: {type(e).__name__}: {e}")

            if not response or response.status_code != 200:
                error_parts = []
                if last_error:
                    error_parts.append(f"error={last_error}")
                if last_status_code:
                    error_parts.append(f"status={last_status_code}")
                if last_response_text:
                    error_parts.append(f"response={last_response_text[:500]}")
                error_detail = "; ".join(error_parts) if error_parts else "No response from API"
                logger.error(f"[AI Signal Gen Stream {request_id}] API failed at round {tool_round}: {error_detail}")
                system_logger.add_log("ERROR", "ai_signal_gen", f"API failed at round {tool_round}", {"error": error_detail, "request_id": request_id})

                # If we have tool calls already, save as interrupted (recoverable)
                if tool_calls_log:
                    reasoning_snapshot = "\n\n---\n\n".join(reasoning_snapshot_parts) if reasoning_snapshot_parts else None
                    assistant_msg = AiSignalMessage(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=f"**[Interrupted at round {tool_round}]** {error_detail}",
                        reasoning_snapshot=reasoning_snapshot,
                        tool_calls_log=json.dumps(tool_calls_log),
                        is_complete=False,
                        interrupt_reason=f"Round {tool_round}: {error_detail}"
                    )
                    db.add(assistant_msg)
                    db.commit()
                    yield _sse_event("interrupted", {
                        "message_id": assistant_msg.id,
                        "conversation_id": conversation.id,
                        "round": tool_round,
                        "error": error_detail
                    })
                else:
                    yield _sse_event("error", {"message": f"API request failed: {error_detail}"})
                return

            # Parse response based on API format
            try:
                response_json = response.json()
                if api_format == 'anthropic':
                    content_blocks = response_json.get("content", [])
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
                    api_tool_calls = tool_uses if tool_uses else None
                else:
                    message = response_json["choices"][0]["message"]
                    tool_calls = message.get("tool_calls", [])
                    reasoning_content = message.get("reasoning_content", "") or extract_reasoning(message)
                    content = message.get("content", "")
                    api_tool_calls = tool_calls if tool_calls else None
            except Exception as e:
                logger.error(f"[AI Signal Gen Stream {request_id}] Failed to parse response: {e}")
                system_logger.add_log("ERROR", "ai_signal_gen", f"Failed to parse response", {"error": str(e), "request_id": request_id})
                yield _sse_event("error", {"message": f"Failed to parse response: {e}"})
                return

            # Strip <thinking> text tags from content
            content, tag_thinking = strip_thinking_tags(content)
            if tag_thinking and not reasoning_content:
                reasoning_content = tag_thinking

            # Send reasoning content if present
            if reasoning_content:
                yield _sse_event("reasoning", {"content": reasoning_content})
                reasoning_snapshot_parts.append(reasoning_content)

            # Send content if present
            if content:
                yield _sse_event("content", {"content": content})

            if api_tool_calls:
                if api_format == 'anthropic':
                    messages.append({
                        "role": "assistant",
                        "content": content or "",
                        "tool_use_blocks": response_json.get("content", [])
                    })
                    for tool_use in api_tool_calls:
                        func_name = tool_use.get("name", "")
                        tool_id = tool_use.get("id", "")
                        func_args = tool_use.get("input", {})
                        yield _sse_event("tool_call", {"name": func_name, "arguments": func_args})
                        tool_result = _execute_tool(db, func_name, func_args)
                        tool_result_parsed = json.loads(tool_result)
                        yield _sse_event("tool_result", {"name": func_name, "result": tool_result_parsed})
                        tool_calls_log.append({"tool": func_name, "args": func_args, "result": tool_result})
                        messages.append({"role": "tool", "tool_call_id": tool_id, "content": tool_result})
                else:
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": content or "",
                        "tool_calls": api_tool_calls
                    }
                    if reasoning_content:
                        assistant_msg_dict["reasoning_content"] = reasoning_content
                    messages.append(assistant_msg_dict)
                    for tool_call in api_tool_calls:
                        func_name = tool_call["function"]["name"]
                        try:
                            func_args = json.loads(tool_call["function"]["arguments"])
                        except json.JSONDecodeError:
                            func_args = {}
                        yield _sse_event("tool_call", {"name": func_name, "arguments": func_args})
                        tool_result = _execute_tool(db, func_name, func_args)
                        tool_result_parsed = json.loads(tool_result)
                        yield _sse_event("tool_result", {"name": func_name, "result": tool_result_parsed})
                        tool_calls_log.append({"tool": func_name, "args": func_args, "result": tool_result})
                        messages.append({"role": "tool", "tool_call_id": tool_call["id"], "content": tool_result})
            else:
                # No tool calls - final response
                # Don't add reasoning here - tool_calls_log already has it via <details> format
                assistant_content = _extract_text_from_message(content) if content else ""
                break

        # Handle limit reached
        if assistant_content is None:
            if 'message' in dir() and message:
                last_content = message.get("content", "")
                if last_content:
                    assistant_content = _extract_text_from_message(last_content)
            if not assistant_content:
                assistant_content = "Processing completed."

        # Extract signal configs and save
        signal_configs = extract_signal_configs(assistant_content)

        for config in signal_configs:
            yield _sse_event("signal_config", {"config": config})

        # Store content without analysis markdown (frontend renders from tool_calls_log/reasoning_snapshot)
        reasoning_snapshot = "\n\n---\n\n".join(reasoning_snapshot_parts) if reasoning_snapshot_parts else None

        # Save assistant message with tool calls log and reasoning
        assistant_msg = AiSignalMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            signal_configs=json.dumps(signal_configs) if signal_configs else None,
            reasoning_snapshot=reasoning_snapshot,
            tool_calls_log=json.dumps(tool_calls_log) if tool_calls_log else None,
            is_complete=True
        )
        db.add(assistant_msg)
        db.commit()

        # Send completion event
        yield _sse_event("done", {
            "success": True,
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "content": assistant_content,
            "signal_configs": signal_configs,
            "elapsed": round(time.time() - start_time, 2),
            "tool_calls_log": tool_calls_log if tool_calls_log else None,
            "reasoning_snapshot": reasoning_snapshot if reasoning_snapshot else None,
            "compression_points": json.loads(conversation.compression_points) if conversation.compression_points else None,
        })

    except Exception as e:
        logger.error(f"[AI Signal Gen Stream {request_id}] Error: {e}", exc_info=True)
        system_logger.add_log("ERROR", "ai_signal_gen", f"Unexpected error in AI signal generation", {"error": str(e), "request_id": request_id})
        db.rollback()
        yield _sse_event("error", {"message": str(e)})
