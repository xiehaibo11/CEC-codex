"""Streaming AI program generation."""
import json
import logging
import time
from typing import Any, Dict, Generator, Optional

import requests
from sqlalchemy.orm import Session

from database.models import Account, AiProgramConversation, AiProgramMessage, TradingProgram
from services.ai_decision_service import (
    build_chat_completion_endpoints,
    build_llm_headers,
    build_llm_payload,
    convert_messages_to_anthropic,
    detect_api_format,
    extract_reasoning,
    strip_thinking_tags,
)
from services.ai_program_generation_config import (
    PROGRAM_SYSTEM_PROMPT,
    PROGRAM_TOOLS,
    PROGRAM_TOOLS_ANTHROPIC,
)
from services.ai_program_generation_core import (
    API_MAX_RETRIES,
    _call_anthropic_streaming,
    _get_retry_delay,
    _should_retry_api,
)
from services.ai_program_generation_execution_tools import _execute_tool
from services.ai_stream_service import format_sse_event

logger = logging.getLogger(__name__)

def generate_program_with_ai_stream(
    db: Session,
    account_id: Optional[int] = None,
    user_message: str = "",
    conversation_id: Optional[int] = None,
    program_id: Optional[int] = None,
    user_id: int = 1,
    llm_config: Optional[Dict[str, Any]] = None
) -> Generator[str, None, None]:
    """
    Generate program code using AI with SSE streaming.
    Yields SSE events for real-time updates.
    """
    import requests
    start_time = time.time()
    request_id = f"program_gen_{int(start_time)}"
    logger.info(f"[AI Program {request_id}] Starting: account_id={account_id}, "
                f"conversation_id={conversation_id}, program_id={program_id}")
    try:
        if llm_config:
            api_config = {
                "base_url": llm_config.get("base_url"),
                "api_key": llm_config.get("api_key"),
                "model": llm_config.get("model"),
                "api_format": llm_config.get("api_format", "openai")
            }
            account = None
        else:
            account = db.query(Account).filter(
                Account.id == account_id,
                Account.account_type == "AI",
                Account.is_deleted != True
            ).first()
            if not account:
                yield format_sse_event("error", {"content": "AI account not found"})
                return
            api_config = {
                "base_url": account.base_url,
                "api_key": account.api_key,
                "model": account.model,
                "api_format": detect_api_format(account.base_url)[1] or "openai"
            }
        conversation = None
        if conversation_id:
            conversation = db.query(AiProgramConversation).filter(
                AiProgramConversation.id == conversation_id,
                AiProgramConversation.user_id == user_id
            ).first()
        if not conversation:
            title = user_message[:50] + "..." if len(user_message) > 50 else user_message
            conversation = AiProgramConversation(
                user_id=user_id,
                program_id=program_id,
                title=title
            )
            db.add(conversation)
            db.flush()
            yield format_sse_event("conversation_created", {"conversation_id": conversation.id})
        user_msg = AiProgramMessage(
            conversation_id=conversation.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        db.flush()
        system_prompt = PROGRAM_SYSTEM_PROMPT
        if program_id:
            program = db.query(TradingProgram).filter(
                TradingProgram.id == program_id,
                TradingProgram.user_id == user_id,
                TradingProgram.is_deleted != True
            ).first()
            if program:
                system_prompt += f"""
You are editing an existing program:
- **Program ID**: {program.id}
- **Program Name**: {program.name}
- **Description**: {program.description or 'No description'}
**IMPORTANT**: Before making any changes, you MUST first call `get_current_code` to understand the existing implementation. Then modify the code based on user's requirements while preserving the overall structure unless explicitly asked to rewrite.
"""
            else:
                system_prompt += """
You are creating a new program. Start fresh and design the strategy based on user's requirements.
"""
        else:
            system_prompt += """
You are creating a new program. Start fresh and design the strategy based on user's requirements.
"""
        from services.ai_context_compression_service import (
            compress_messages, update_compression_points,
            restore_tool_calls_to_messages,
            get_last_compression_point, filter_messages_by_compression,
        )
        messages = [{"role": "system", "content": system_prompt}]
        cp = get_last_compression_point(conversation)
        if cp and cp.get("summary"):
            messages.append({
                "role": "system",
                "content": f"[Previous conversation summary]\n{cp['summary']}"
            })
        history = db.query(AiProgramMessage).filter(
            AiProgramMessage.conversation_id == conversation.id,
            AiProgramMessage.id != user_msg.id
        ).order_by(AiProgramMessage.created_at).limit(100).all()
        history = filter_messages_by_compression(history, cp)
        last_message_id = history[-1].id if history else None
        history_dicts = [
            {
                "role": m.role,
                "content": m.content,
                "tool_calls_log": m.tool_calls_log,
                "reasoning_snapshot": m.reasoning_snapshot,
            }
            for m in history
        ]
        restored = restore_tool_calls_to_messages(history_dicts, api_config.get("api_format", "openai"), model=api_config.get("model", ""))
        messages.extend(restored)
        messages.append({"role": "user", "content": user_message})
        result = compress_messages(messages, api_config, db=db)
        messages = result["messages"]
        if result["compressed"] and result["summary"] and last_message_id:
            update_compression_points(
                conversation, last_message_id,
                result["summary"], result["compressed_at"], db
            )
        endpoint, api_format = detect_api_format(api_config["base_url"])
        if not endpoint:
            yield format_sse_event("error", {"content": "Invalid API configuration"})
            return
        if api_format == 'anthropic':
            endpoints = [endpoint]
        else:
            endpoints = build_chat_completion_endpoints(api_config["base_url"], api_config["model"])
            if not endpoints:
                yield format_sse_event("error", {"content": "Invalid API configuration"})
                return
        headers = build_llm_headers(api_format, api_config["api_key"], api_config["base_url"])
        max_rounds = 15
        tool_round = 0
        tool_calls_log = []
        final_content = ""
        reasoning_snapshot = ""
        code_suggestion = None
        anthropic_tool_use_blocks = []
        assistant_msg = AiProgramMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="",  # Will be updated each round
            is_complete=False  # Mark as incomplete until done
        )
        db.add(assistant_msg)
        db.flush()
        while tool_round < max_rounds:
            tool_round += 1
            is_last = tool_round == max_rounds
            yield format_sse_event("tool_round", {"round": tool_round, "max": max_rounds})
            if api_format == 'anthropic':
                system_prompt, anthropic_messages = convert_messages_to_anthropic(messages)
                tools_for_round = PROGRAM_TOOLS_ANTHROPIC if not is_last else None
                payload = build_llm_payload(
                    model=api_config["model"],
                    messages=[{"role": "system", "content": system_prompt}] + anthropic_messages,
                    api_format=api_format,
                    tools=tools_for_round,
                )
            else:
                tools_for_round = PROGRAM_TOOLS if not is_last else None
                payload = build_llm_payload(
                    model=api_config["model"],
                    messages=messages,
                    api_format=api_format,
                    tools=tools_for_round,
                    tool_choice="auto" if not is_last else None,
                )
            logger.info(f"[AI Program {request_id}] Round {tool_round}: Calling API with {len(endpoints)} endpoints, format={api_format}")
            if api_format == 'anthropic' and tool_round > 1:
                logger.warning(f"[AI Program {request_id}] Anthropic round {tool_round} payload messages count: {len(payload.get('messages', []))}")
                for i, m in enumerate(payload.get('messages', [])):
                    role = m.get('role', 'unknown')
                    content = m.get('content', '')
                    if isinstance(content, list):
                        content_summary = f"[{len(content)} blocks: {[b.get('type', '?') for b in content]}]"
                    else:
                        content_summary = f"str({len(str(content))} chars)"
                    logger.warning(f"[AI Program {request_id}]   msg[{i}]: role={role}, content={content_summary}")
            response = None
            resp_json = None  # For Anthropic streaming, we get parsed result directly
            last_error = None
            last_status_code = None
            last_response_text = None  # Store full response text for error logging
            for retry_attempt in range(API_MAX_RETRIES):
                response = None
                resp_json = None
                for endpoint in endpoints:
                    try:
                        logger.info(f"[AI Program {request_id}] Trying endpoint: {endpoint}" +
                                   (f" (retry {retry_attempt + 1}/{API_MAX_RETRIES})" if retry_attempt > 0 else ""))
                        if api_format == 'anthropic':
                            resp_json = _call_anthropic_streaming(endpoint, payload, headers, timeout=180)
                            logger.info(f"[AI Program {request_id}] Anthropic streaming response received")
                            break  # Success
                        else:
                            response = requests.post(endpoint, json=payload, headers=headers, timeout=120)
                            last_status_code = response.status_code
                            last_response_text = response.text[:2000] if response.text else None
                            logger.info(f"[AI Program {request_id}] Response status: {response.status_code}")
                            if response.status_code != 200:
                                last_error = f"HTTP {response.status_code}"
                                logger.warning(f"[AI Program {request_id}] Non-200 response from {endpoint}: {response.status_code} - {response.text[:500]}")
                            if response.status_code == 200:
                                break
                    except requests.exceptions.Timeout as e:
                        last_error = f"Timeout after 120s: {str(e)}"
                        logger.warning(f"[AI Program {request_id}] Endpoint {endpoint} timeout: {e}")
                    except requests.exceptions.ConnectionError as e:
                        last_error = f"Connection error: {str(e)}"
                        logger.warning(f"[AI Program {request_id}] Endpoint {endpoint} connection error: {e}")
                    except Exception as e:
                        last_error = f"{type(e).__name__}: {str(e)}"
                        logger.warning(f"[AI Program {request_id}] Endpoint {endpoint} error: {type(e).__name__}: {e}")
                if api_format == 'anthropic' and resp_json:
                    break  # Anthropic streaming succeeded
                if api_format != 'anthropic' and response and response.status_code == 200:
                    break
                if not _should_retry_api(last_status_code, last_error):
                    logger.info(f"[AI Program {request_id}] Error not retryable, giving up")
                    break
                if retry_attempt < API_MAX_RETRIES - 1:
                    delay = _get_retry_delay(retry_attempt)
                    logger.warning(f"[AI Program {request_id}] Retrying in {delay:.1f}s (attempt {retry_attempt + 2}/{API_MAX_RETRIES})")
                    yield format_sse_event("retry", {"attempt": retry_attempt + 2, "max_retries": API_MAX_RETRIES})
                    time.sleep(delay)
            if api_format == 'anthropic':
                if not resp_json:
                    error_parts = []
                    if last_error:
                        error_parts.append(f"error={last_error}")
                    if last_status_code:
                        error_parts.append(f"status={last_status_code}")
                    if last_response_text:
                        error_parts.append(f"response={last_response_text[:500]}")
                    error_detail = "; ".join(error_parts) if error_parts else "No response from API"
                    logger.error(f"[AI Program {request_id}] API failed at round {tool_round}: {error_detail}")
                    if tool_calls_log:
                        assistant_msg.content = f"**[Interrupted at round {tool_round}]** {error_detail}"
                        assistant_msg.tool_calls_log = json.dumps(tool_calls_log)
                        assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
                        assistant_msg.is_complete = False
                        assistant_msg.interrupt_reason = f"Round {tool_round}: {error_detail}"
                        db.commit()
                        yield format_sse_event("interrupted", {"message_id": assistant_msg.id, "round": tool_round, "error": error_detail})
                    else:
                        db.delete(assistant_msg)
                        db.commit()
                        yield format_sse_event("error", {"content": f"API request failed: {error_detail}"})
                    return
            else:
                if not response or response.status_code != 200:
                    error_parts = []
                    if last_error:
                        error_parts.append(f"error={last_error}")
                    if last_status_code:
                        error_parts.append(f"status={last_status_code}")
                    if last_response_text:
                        error_parts.append(f"response={last_response_text[:500]}")
                    elif response and response.text:
                        error_parts.append(f"response={response.text[:500]}")
                    error_detail = "; ".join(error_parts) if error_parts else "No response from API"
                    logger.error(f"[AI Program {request_id}] API failed at round {tool_round}: {error_detail}")
                    if tool_calls_log:
                        assistant_msg.content = f"**[Interrupted at round {tool_round}]** {error_detail}"
                        assistant_msg.tool_calls_log = json.dumps(tool_calls_log)
                        assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
                        assistant_msg.is_complete = False
                        assistant_msg.interrupt_reason = f"Round {tool_round}: {error_detail}"
                        db.commit()
                        yield format_sse_event("interrupted", {"message_id": assistant_msg.id, "round": tool_round, "error": error_detail})
                    else:
                        db.delete(assistant_msg)
                        db.commit()
                        yield format_sse_event("error", {"content": f"API request failed: {error_detail}"})
                    return
                resp_json = response.json()
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
                content, tag_thinking = strip_thinking_tags(content)
                if tag_thinking and not reasoning_content:
                    reasoning_content = tag_thinking
                    reasoning_snapshot += f"\n[Round {tool_round}]\n{tag_thinking}"
                if tool_uses:
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": content,
                        "tool_use_blocks": content_blocks  # Store for conversion
                    }
                    messages.append(assistant_msg_dict)
                    for tu in tool_uses:
                        fn_name = tu.get("name", "")
                        fn_args = tu.get("input", {})
                        tool_use_id = tu.get("id", "")
                        if fn_args == "":
                            fn_args = {}
                        yield format_sse_event("tool_call", {"name": fn_name, "args": fn_args})
                        result = _execute_tool(fn_name, fn_args, db, program_id, user_id)
                        tool_calls_log.append({"tool": fn_name, "args": fn_args, "result": result[:1000]})
                        if fn_name == "suggest_save_code":
                            try:
                                suggestion = json.loads(result)
                                if suggestion.get("type") == "save_suggestion":
                                    code_suggestion = json.dumps({
                                        "code": suggestion.get("code", ""),
                                        "name": suggestion.get("name", ""),
                                        "description": suggestion.get("description", "")
                                    })
                                    yield format_sse_event("save_suggestion", {"data": suggestion})
                            except:
                                pass
                        yield format_sse_event("tool_result", {"name": fn_name, "result": result[:500]})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id,
                            "content": result
                        })
                else:
                    final_content = content or ""
                    yield format_sse_event("content", {"content": final_content})
                    break
            else:
                message = resp_json["choices"][0]["message"]
                tool_calls = message.get("tool_calls", [])
                reasoning_content = message.get("reasoning_content", "")
                content = message.get("content", "")
                if reasoning_content:
                    reasoning_snapshot += f"\n[Round {tool_round}]\n{reasoning_content}"
                    yield format_sse_event("reasoning", {"content": reasoning_content[:500]})
                else:
                    reasoning = extract_reasoning(message)
                    if reasoning:
                        reasoning_snapshot += f"\n[Round {tool_round}]\n{reasoning}"
                        yield format_sse_event("reasoning", {"content": reasoning[:500]})
                content, tag_thinking = strip_thinking_tags(content)
                if tag_thinking and not reasoning_content:
                    reasoning_content = tag_thinking
                    reasoning_snapshot += f"\n[Round {tool_round}]\n{tag_thinking}"
                if tool_calls:
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": content or "",
                        "tool_calls": tool_calls
                    }
                    if reasoning_content:
                        assistant_msg_dict["reasoning_content"] = reasoning_content
                    messages.append(assistant_msg_dict)
                    for tc in tool_calls:
                        fn_name = tc["function"]["name"]
                        try:
                            fn_args = json.loads(tc["function"]["arguments"])
                        except:
                            fn_args = {}
                        yield format_sse_event("tool_call", {"name": fn_name, "args": fn_args})
                        result = _execute_tool(fn_name, fn_args, db, program_id, user_id)
                        tool_calls_log.append({"tool": fn_name, "args": fn_args, "result": result[:1000]})
                        if fn_name == "suggest_save_code":
                            try:
                                suggestion = json.loads(result)
                                if suggestion.get("type") == "save_suggestion":
                                    code_suggestion = json.dumps({
                                        "code": suggestion.get("code", ""),
                                        "name": suggestion.get("name", ""),
                                        "description": suggestion.get("description", "")
                                    })
                                    yield format_sse_event("save_suggestion", {"data": suggestion})
                            except:
                                pass
                        yield format_sse_event("tool_result", {"name": fn_name, "result": result[:500]})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result
                        })
                else:
                    final_content = content or ""
                    yield format_sse_event("content", {"content": final_content})
                    break
            if tool_calls_log:
                assistant_msg.content = "Processing..."
                assistant_msg.tool_calls_log = json.dumps(tool_calls_log)
                assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
                db.commit()
        if not final_content:
            if 'message' in dir() and message:
                last_content = message.get("content", "")
                if last_content:
                    final_content = last_content
            if not final_content:
                final_content = "Processing completed."
        assistant_msg.content = final_content
        assistant_msg.code_suggestion = code_suggestion
        assistant_msg.reasoning_snapshot = reasoning_snapshot if reasoning_snapshot else None
        assistant_msg.tool_calls_log = json.dumps(tool_calls_log) if tool_calls_log else None
        assistant_msg.is_complete = True
        db.commit()
        done_data = {
            "message_id": assistant_msg.id,
            "content": final_content,
            "conversation_id": conversation.id,
            "tool_calls_log": tool_calls_log if tool_calls_log else None,
            "reasoning_snapshot": reasoning_snapshot if reasoning_snapshot else None,
            "compression_points": json.loads(conversation.compression_points) if conversation.compression_points else None,
        }
        yield format_sse_event("done", done_data)
    except Exception as e:
        logger.error(f"[AI Program {request_id}] Error: {e}")
        db.rollback()
        yield format_sse_event("error", {"content": str(e)})
