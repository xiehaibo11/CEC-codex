"""Synchronous AI signal generation."""
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
from services.ai_signal_generation_tool_prediction import _execute_tool

logger = logging.getLogger(__name__)

def generate_signal_with_ai(
    db: Session,
    account_id: int,
    user_message: str,
    conversation_id: Optional[int] = None,
    user_id: int = 1
) -> Dict[str, Any]:
    """
    Generate signal configuration using AI.
    Follows the same pattern as ai_prompt_generation_service.generate_prompt_with_ai
    """
    start_time = time.time()
    request_id = f"signal_gen_{int(start_time)}"

    logger.info(f"[AI Signal Gen {request_id}] Starting: account_id={account_id}, "
                f"conversation_id={conversation_id}, user_message_length={len(user_message)}")

    try:
        # Get the specified AI account
        account = db.query(Account).filter(
            Account.id == account_id,
            Account.account_type == "AI",
            Account.is_deleted != True
        ).first()

        if not account:
            return {"success": False, "error": "AI account not found"}

        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = db.query(AiSignalConversation).filter(
                AiSignalConversation.id == conversation_id,
                AiSignalConversation.user_id == user_id
            ).first()
            if not conversation:
                logger.warning(f"[AI Signal Gen {request_id}] Conversation {conversation_id} not found")

        if not conversation:
            title = user_message[:50] + "..." if len(user_message) > 50 else user_message
            conversation = AiSignalConversation(user_id=user_id, title=title)
            db.add(conversation)
            db.flush()
            logger.info(f"[AI Signal Gen {request_id}] Created new conversation: id={conversation.id}")

        # Save user message
        user_msg = AiSignalMessage(
            conversation_id=conversation.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        db.flush()

        # Build message history with compression support
        from services.ai_context_compression_service import compress_messages, update_compression_points

        messages = [{"role": "system", "content": SIGNAL_SYSTEM_PROMPT}]

        # Get more messages, compression will handle limits
        history_messages = db.query(AiSignalMessage).filter(
            AiSignalMessage.conversation_id == conversation.id,
            AiSignalMessage.id != user_msg.id
        ).order_by(AiSignalMessage.created_at).limit(100).all()

        last_message_id = None
        for msg in history_messages:
            messages.append({"role": msg.role, "content": msg.content})
            last_message_id = msg.id

        messages.append({"role": "user", "content": user_message})

        # Apply compression if needed
        api_config = {
            "base_url": account.base_url,
            "api_key": account.api_key,
            "model": account.model,
            "api_format": detect_api_format(account.base_url)[1] or "openai"
        }
        comp_result = compress_messages(messages, api_config, db=db)
        messages = comp_result["messages"]

        # Update compression_points if compression occurred
        if comp_result["compressed"] and comp_result["summary"] and last_message_id:
            update_compression_points(
                conversation, last_message_id,
                comp_result["summary"], comp_result["compressed_at"], db
            )

        logger.info(f"[AI Signal Gen {request_id}] Built message context: {len(messages)} messages total")

        # Call LLM API with Function Calling support
        api_format = api_config["api_format"]
        endpoint, _ = detect_api_format(account.base_url)
        if api_format == 'anthropic':
            endpoints = [endpoint] if endpoint else []
        else:
            endpoints = build_chat_completion_endpoints(account.base_url, account.model)
        if not endpoints:
            return {"success": False, "error": "Invalid base_url configuration"}

        # Use unified headers builder (see build_llm_headers in ai_decision_service)
        headers = build_llm_headers(api_format, account.api_key, account.base_url)

        # Function Calling loop (max 30 rounds, last round forces no tools)
        max_tool_rounds = 30
        tool_round = 0
        assistant_content = None

        while tool_round < max_tool_rounds:
            tool_round += 1
            is_last_round = (tool_round == max_tool_rounds)
            logger.info(f"[AI Signal Gen {request_id}] Tool round {tool_round}/{max_tool_rounds} (last={is_last_round})")

            # On last round, force model to give final answer without tools
            if is_last_round:
                messages.append({
                    "role": "user",
                    "content": "You have used enough tools. Now output the final signal configuration based on your analysis. Include the ```signal-config``` block."
                })

            # Use unified payload builder (see build_llm_payload in ai_decision_service)
            if api_format == 'anthropic':
                sys_prompt, anthropic_messages = convert_messages_to_anthropic(messages)
                tools_for_round = convert_tools_to_anthropic(SIGNAL_TOOLS) if not is_last_round else None
                request_payload = build_llm_payload(
                    model=account.model,
                    messages=[{"role": "system", "content": sys_prompt}] + anthropic_messages,
                    api_format=api_format,
                    tools=tools_for_round,
                )
            else:
                request_payload = build_llm_payload(
                    model=account.model,
                    messages=messages,
                    api_format=api_format,
                    tools=SIGNAL_TOOLS if not is_last_round else None,
                    tool_choice="auto" if not is_last_round else None,
                )

            response = None
            last_error = None
            last_status_code = None
            last_response_text = None

            for endpoint in endpoints:
                try:
                    logger.info(f"[AI Signal Gen {request_id}] Trying endpoint: {endpoint}")
                    api_start = time.time()
                    response = requests.post(endpoint, json=request_payload, headers=headers, timeout=120)
                    api_elapsed = time.time() - api_start
                    last_status_code = response.status_code
                    last_response_text = response.text[:2000] if response.text else None

                    if response.status_code == 200:
                        logger.info(f"[AI Signal Gen {request_id}] Success in {api_elapsed:.2f}s")
                        break
                    else:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(f"[AI Signal Gen {request_id}] Endpoint failed: {response.status_code} - {response.text[:500]}")
                except requests.exceptions.Timeout as e:
                    last_error = f"Timeout after 120s: {str(e)}"
                    logger.warning(f"[AI Signal Gen {request_id}] Timeout on {endpoint}: {e}")
                except requests.exceptions.ConnectionError as e:
                    last_error = f"Connection error: {str(e)}"
                    logger.warning(f"[AI Signal Gen {request_id}] Connection error on {endpoint}: {e}")
                except Exception as e:
                    last_error = f"{type(e).__name__}: {str(e)}"
                    logger.warning(f"[AI Signal Gen {request_id}] Error on {endpoint}: {type(e).__name__}: {e}")

            if not response or response.status_code != 200:
                error_parts = []
                if last_error:
                    error_parts.append(f"error={last_error}")
                if last_status_code:
                    error_parts.append(f"status={last_status_code}")
                if last_response_text:
                    error_parts.append(f"response={last_response_text[:500]}")
                error_detail = "; ".join(error_parts) if error_parts else "No response from API"
                logger.error(f"[AI Signal Gen {request_id}] API failed: {error_detail}")
                return {"success": False, "error": f"All endpoints failed: {error_detail}"}

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
                    tool_calls = None
                    api_tool_calls = tool_uses if tool_uses else None
                else:
                    message = response_json["choices"][0]["message"]
                    tool_calls = message.get("tool_calls", [])
                    reasoning_content = message.get("reasoning_content", "") or extract_reasoning(message)
                    content = message.get("content", "")
                    api_tool_calls = tool_calls if tool_calls else None
            except Exception as e:
                logger.error(f"[AI Signal Gen {request_id}] Failed to parse response: {e}")
                return {"success": False, "error": f"Failed to parse AI response: {str(e)}"}

            # Strip <thinking> text tags from content
            content, tag_thinking = strip_thinking_tags(content)
            if tag_thinking and not reasoning_content:
                reasoning_content = tag_thinking

            # Log for debugging
            logger.info(f"[AI Signal Gen {request_id}] Response: tool_calls={len(api_tool_calls) if api_tool_calls else 0}, "
                       f"has_reasoning={bool(reasoning_content)}, has_content={bool(content)}")

            if api_tool_calls:
                if api_format == 'anthropic':
                    # Anthropic format: tool_use blocks
                    messages.append({
                        "role": "assistant",
                        "content": content or "",
                        "tool_use_blocks": response_json.get("content", [])
                    })
                    for tool_use in api_tool_calls:
                        func_name = tool_use.get("name", "")
                        tool_id = tool_use.get("id", "")
                        func_args = tool_use.get("input", {})
                        logger.info(f"[AI Signal Gen {request_id}] Executing tool: {func_name}({func_args})")
                        tool_result = _execute_tool(db, func_name, func_args)
                        logger.info(f"[AI Signal Gen {request_id}] Tool result: {tool_result[:200]}...")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": tool_result
                        })
                else:
                    # OpenAI format: tool_calls array
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
                        logger.info(f"[AI Signal Gen {request_id}] Executing tool: {func_name}({func_args})")
                        tool_result = _execute_tool(db, func_name, func_args)
                        logger.info(f"[AI Signal Gen {request_id}] Tool result: {tool_result[:200]}...")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_result
                        })
                # Continue loop for next round
            else:
                # No tool calls - AI returned final response
                # Combine reasoning_content and content for full response
                full_content = ""
                if reasoning_content:
                    full_content += f"**Reasoning:**\n{reasoning_content}\n\n"
                if content:
                    full_content += content
                assistant_content = _extract_text_from_message(full_content) if full_content else ""
                break

        # If we exhausted tool rounds, use the last content we received
        if assistant_content is None:
            # Try to get content from the last message in the loop
            if 'message' in dir() and message:
                last_content = message.get("content", "")
                last_reasoning = message.get("reasoning_content", "")
                if last_content or last_reasoning:
                    full_content = ""
                    if last_reasoning:
                        full_content += f"**Reasoning:**\n{last_reasoning}\n\n"
                    if last_content:
                        full_content += last_content
                    assistant_content = _extract_text_from_message(full_content)
                    logger.info(f"[AI Signal Gen {request_id}] Using last round content after limit reached")

            if not assistant_content:
                assistant_content = "Tool calling limit reached. Please try again with a simpler request."

        # Extract signal configs from response
        signal_configs = extract_signal_configs(assistant_content)

        # Save assistant message
        assistant_msg = AiSignalMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            signal_configs=json.dumps(signal_configs) if signal_configs else None
        )
        db.add(assistant_msg)
        db.commit()

        total_elapsed = time.time() - start_time
        logger.info(f"[AI Signal Gen {request_id}] Completed in {total_elapsed:.2f}s: "
                   f"conversation_id={conversation.id}, configs_found={len(signal_configs)}")

        return {
            "success": True,
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "content": assistant_content,
            "signal_configs": signal_configs
        }

    except Exception as e:
        logger.error(f"[AI Signal Gen {request_id}] Unexpected error: {type(e).__name__}: {str(e)}",
                    exc_info=True)
        db.rollback()
        return {"success": False, "error": f"Internal error: {type(e).__name__}"}
