"""Attribution analysis streaming + conversation/message retrieval.

Drives the LLM Function Calling loop that produces diagnosis cards/prompt
suggestions, extracts structured results, and exposes conversation history APIs.
"""

import json
import logging
import re
import time
import requests
from typing import Dict, List, Optional, Any, Generator

from sqlalchemy.orm import Session

from database.models import (
    AiAttributionConversation, AiAttributionMessage, Account
)
from services.ai_decision_service import (
    build_chat_completion_endpoints, detect_api_format, _extract_text_from_message,
    build_llm_payload, build_llm_headers, extract_reasoning,
    convert_tools_to_anthropic, convert_messages_to_anthropic, strip_thinking_tags
)
from services.ai_attribution_service.prompts import ATTRIBUTION_SYSTEM_PROMPT
from services.ai_attribution_service.tools_schema import ATTRIBUTION_TOOLS
from services.ai_attribution_service.tools import _execute_tool

logger = logging.getLogger(__name__)


def extract_diagnosis_results(content: str) -> List[Dict]:
    """Extract diagnosis cards and prompt suggestions from AI response"""
    results = []

    # Extract diagnosis cards
    diagnosis_pattern = r"```diagnosis-card\s*([\s\S]*?)```"
    for match in re.findall(diagnosis_pattern, content):
        try:
            card = json.loads(match.strip())
            card["_type"] = "diagnosis"
            results.append(card)
        except:
            pass

    # Extract prompt suggestions
    suggestion_pattern = r"```prompt-suggestion\s*([\s\S]*?)```"
    for match in re.findall(suggestion_pattern, content):
        try:
            suggestion = json.loads(match.strip())
            suggestion["_type"] = "prompt_suggestion"
            results.append(suggestion)
        except:
            pass

    return results


def generate_attribution_analysis_stream(
    db: Session,
    account_id: Optional[int] = None,
    user_message: str = "",
    conversation_id: Optional[int] = None,
    user_id: int = 1,
    llm_config: Optional[Dict[str, Any]] = None
) -> Generator[str, None, None]:
    """Generate attribution analysis with SSE streaming"""
    start_time = time.time()
    request_id = f"attr_analysis_{int(start_time)}"

    logger.info(f"[AI Attribution {request_id}] Starting: account_id={account_id}")

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
            account = None
        else:
            # Original logic: get from AI account
            account = db.query(Account).filter(
                Account.id == account_id,
                Account.account_type == "AI"
            ).first()

            if not account:
                yield f"event: error\ndata: {json.dumps({'message': 'AI account not found'})}\n\n"
                return

            api_config = {
                "base_url": account.base_url,
                "api_key": account.api_key,
                "model": account.model,
                "api_format": detect_api_format(account.base_url)[1] or "openai"
            }

        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = db.query(AiAttributionConversation).filter(
                AiAttributionConversation.id == conversation_id,
                AiAttributionConversation.user_id == user_id
            ).first()

        is_new_conversation = False
        if not conversation:
            title = user_message[:50] + "..." if len(user_message) > 50 else user_message
            conversation = AiAttributionConversation(user_id=user_id, title=title)
            db.add(conversation)
            db.flush()
            is_new_conversation = True

        if is_new_conversation:
            yield f"event: conversation_created\ndata: {json.dumps({'conversation_id': conversation.id})}\n\n"

        # Save user message
        user_msg = AiAttributionMessage(
            conversation_id=conversation.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        db.flush()

        yield f"event: status\ndata: {json.dumps({'message': 'Analyzing...'})}\n\n"

        # Build message history with compression support
        from services.ai_context_compression_service import (
            compress_messages, update_compression_points,
            restore_tool_calls_to_messages,
            get_last_compression_point, filter_messages_by_compression,
        )

        messages = [{"role": "system", "content": ATTRIBUTION_SYSTEM_PROMPT}]

        # Check compression points - inject summary for compressed messages
        cp = get_last_compression_point(conversation)
        if cp and cp.get("summary"):
            messages.append({
                "role": "system",
                "content": f"[Previous conversation summary]\n{cp['summary']}"
            })

        # Load history, filter by compression point
        history = db.query(AiAttributionMessage).filter(
            AiAttributionMessage.conversation_id == conversation.id,
            AiAttributionMessage.id != user_msg.id
        ).order_by(AiAttributionMessage.created_at).limit(100).all()

        history = filter_messages_by_compression(history, cp)

        last_message_id = history[-1].id if history else None

        # Restore tool_calls into proper LLM message format
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

        # Apply compression if needed (api_config already set above)
        comp_result = compress_messages(messages, api_config, db=db)
        messages = comp_result["messages"]

        # Update compression_points if compression occurred
        if comp_result["compressed"] and comp_result["summary"] and last_message_id:
            update_compression_points(
                conversation, last_message_id,
                comp_result["summary"], comp_result["compressed_at"], db
            )

        # Call LLM with Function Calling
        api_format = api_config.get("api_format", "openai")
        if api_format == 'anthropic':
            ep, _ = detect_api_format(api_config["base_url"])
            endpoints = [ep] if ep else []
        else:
            endpoints = build_chat_completion_endpoints(api_config["base_url"], api_config["model"])
        if not endpoints:
            yield f"event: error\ndata: {json.dumps({'message': 'Invalid API configuration'})}\n\n"
            return

        # Use unified headers builder (see build_llm_headers in ai_decision_service)
        headers = build_llm_headers(api_format, api_config["api_key"], api_config["base_url"])

        # Function calling loop
        max_rounds = 15
        assistant_content = None

        # Collect reasoning and analysis log for storage
        all_reasoning_parts = []
        tool_calls_log = []

        for round_num in range(max_rounds):
            is_last = (round_num == max_rounds - 1)

            yield f"event: tool_round\ndata: {json.dumps({'round': round_num + 1, 'max_rounds': max_rounds})}\n\n"

            if is_last:
                messages.append({
                    "role": "user",
                    "content": "Now provide your final analysis with diagnosis cards and suggestions."
                })

            # Use unified payload builder (see build_llm_payload in ai_decision_service)
            if api_format == 'anthropic':
                sys_prompt, anthropic_messages = convert_messages_to_anthropic(messages)
                tools_for_round = convert_tools_to_anthropic(ATTRIBUTION_TOOLS) if not is_last else None
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
                    tools=ATTRIBUTION_TOOLS if not is_last else None,
                    tool_choice="auto" if not is_last else None,
                )

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
                        logger.warning(f"[AI Attribution] Endpoint failed: {response.status_code} - {response.text[:500]}")
                except requests.exceptions.Timeout as e:
                    last_error = f"Timeout after 120s: {str(e)}"
                    logger.warning(f"[AI Attribution] Endpoint timeout: {e}")
                except requests.exceptions.ConnectionError as e:
                    last_error = f"Connection error: {str(e)}"
                    logger.warning(f"[AI Attribution] Connection error: {e}")
                except Exception as e:
                    last_error = f"{type(e).__name__}: {str(e)}"
                    logger.warning(f"[AI Attribution] Endpoint error: {type(e).__name__}: {e}")

            if not response or response.status_code != 200:
                error_parts = []
                if last_error:
                    error_parts.append(f"error={last_error}")
                if last_status_code:
                    error_parts.append(f"status={last_status_code}")
                if last_response_text:
                    error_parts.append(f"response={last_response_text[:500]}")
                error_detail = "; ".join(error_parts) if error_parts else "No response from API"
                logger.error(f"[AI Attribution] API failed at round {round_num + 1}: {error_detail}")

                if tool_calls_log:
                    reasoning_snapshot = "\n\n---\n\n".join(all_reasoning_parts) if all_reasoning_parts else None
                    assistant_msg = AiAttributionMessage(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=f"**[Interrupted at round {round_num + 1}]** {error_detail}",
                        reasoning_snapshot=reasoning_snapshot,
                        tool_calls_log=json.dumps(tool_calls_log),
                        is_complete=False,
                        interrupt_reason=f"Round {round_num + 1}: {error_detail}"
                    )
                    db.add(assistant_msg)
                    db.commit()
                    yield f"event: interrupted\ndata: {json.dumps({'message_id': assistant_msg.id, 'conversation_id': conversation.id, 'round': round_num + 1, 'error': error_detail})}\n\n"
                else:
                    yield f"event: error\ndata: {json.dumps({'message': f'API request failed: {error_detail}'})}\n\n"
                return

            resp_json = response.json()

            # Parse response based on API format
            if api_format == 'anthropic':
                content_blocks = resp_json.get("content", [])
                tool_uses = []
                content = ""
                reasoning = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        content += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_uses.append(block)
                    elif block.get("type") == "thinking":
                        t = block.get("thinking", "")
                        if t:
                            reasoning += t
                api_tool_calls = tool_uses if tool_uses else None
            else:
                message = resp_json["choices"][0]["message"]
                tool_calls = message.get("tool_calls", [])
                content = message.get("content", "")
                reasoning = message.get("reasoning_content", "") or extract_reasoning(message)
                api_tool_calls = tool_calls if tool_calls else None

            # Strip <thinking> text tags from content
            content, tag_thinking = strip_thinking_tags(content)
            if tag_thinking and not reasoning:
                reasoning = tag_thinking

            if reasoning:
                yield f"event: reasoning\ndata: {json.dumps({'content': reasoning[:200]})}\n\n"
                all_reasoning_parts.append(reasoning)

            if api_tool_calls:
                if api_format == 'anthropic':
                    messages.append({
                        "role": "assistant",
                        "content": content or "",
                        "tool_use_blocks": resp_json.get("content", [])
                    })
                    for tool_use in api_tool_calls:
                        func_name = tool_use.get("name", "")
                        tool_id = tool_use.get("id", "")
                        func_args = tool_use.get("input", {})
                        yield f"event: tool_call\ndata: {json.dumps({'name': func_name, 'arguments': func_args})}\n\n"
                        result = _execute_tool(db, func_name, func_args)
                        yield f"event: tool_result\ndata: {json.dumps({'name': func_name, 'result': json.loads(result)})}\n\n"
                        tool_calls_log.append({"tool": func_name, "args": func_args, "result": result})
                        messages.append({"role": "tool", "tool_call_id": tool_id, "content": result})
                else:
                    msg_dict = {"role": "assistant", "content": content or "", "tool_calls": api_tool_calls}
                    if reasoning:
                        msg_dict["reasoning_content"] = reasoning
                    messages.append(msg_dict)
                    for tc in api_tool_calls:
                        func_name = tc["function"]["name"]
                        try:
                            func_args = json.loads(tc["function"]["arguments"])
                        except:
                            func_args = {}
                        yield f"event: tool_call\ndata: {json.dumps({'name': func_name, 'arguments': func_args})}\n\n"
                        result = _execute_tool(db, func_name, func_args)
                        yield f"event: tool_result\ndata: {json.dumps({'name': func_name, 'result': json.loads(result)})}\n\n"
                        tool_calls_log.append({"tool": func_name, "args": func_args, "result": result})
                        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            else:
                # Final response - only use content, not reasoning
                assistant_content = _extract_text_from_message(content) if content else ""
                break

        if not assistant_content:
            assistant_content = "Analysis completed but no final response generated."

        # Extract diagnosis results
        diagnosis_results = extract_diagnosis_results(assistant_content)

        # Save assistant message with reasoning and tool calls log
        reasoning_snapshot = "\n\n---\n\n".join(all_reasoning_parts) if all_reasoning_parts else None
        tool_calls_log_json = json.dumps(tool_calls_log) if tool_calls_log else None

        assistant_msg = AiAttributionMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            diagnosis_result=json.dumps(diagnosis_results) if diagnosis_results else None,
            reasoning_snapshot=reasoning_snapshot,
            tool_calls_log=tool_calls_log_json,
            is_complete=True
        )
        db.add(assistant_msg)
        db.commit()

        # Send final response
        yield f"event: content\ndata: {json.dumps({'content': assistant_content})}\n\n"
        yield f"event: done\ndata: {json.dumps({'conversation_id': conversation.id, 'message_id': assistant_msg.id, 'content': assistant_content, 'diagnosis_results': diagnosis_results, 'tool_calls_log': json.loads(tool_calls_log_json) if tool_calls_log_json else None, 'reasoning_snapshot': reasoning_snapshot if reasoning_snapshot else None, 'compression_points': json.loads(conversation.compression_points) if conversation.compression_points else None})}\n\n"

    except Exception as e:
        logger.error(f"[AI Attribution {request_id}] Error: {e}", exc_info=True)
        db.rollback()
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"


def get_attribution_conversations(db: Session, user_id: int = 1, limit: int = 20) -> List[Dict]:
    """Get list of attribution analysis conversations"""
    conversations = db.query(AiAttributionConversation).filter(
        AiAttributionConversation.user_id == user_id
    ).order_by(AiAttributionConversation.updated_at.desc()).limit(limit).all()

    return [{
        "id": c.id,
        "title": c.title,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None
    } for c in conversations]


def get_attribution_messages(db: Session, conversation_id: int, user_id: int = 1) -> List[Dict]:
    """Get messages for a specific conversation"""
    conversation = db.query(AiAttributionConversation).filter(
        AiAttributionConversation.id == conversation_id,
        AiAttributionConversation.user_id == user_id
    ).first()

    if not conversation:
        return []

    messages = db.query(AiAttributionMessage).filter(
        AiAttributionMessage.conversation_id == conversation_id
    ).order_by(AiAttributionMessage.created_at).all()

    result = []
    for m in messages:
        msg_dict = {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        if m.diagnosis_result:
            try:
                msg_dict["diagnosis_results"] = json.loads(m.diagnosis_result)
            except:
                pass
        # Include reasoning and tool calls log for history display
        if m.reasoning_snapshot:
            msg_dict["reasoning_snapshot"] = m.reasoning_snapshot
        if m.tool_calls_log:
            try:
                msg_dict["tool_calls_log"] = json.loads(m.tool_calls_log)
            except:
                pass
        if hasattr(m, 'is_complete'):
            msg_dict["is_complete"] = m.is_complete if m.is_complete is not None else True
        result.append(msg_dict)

    return result
