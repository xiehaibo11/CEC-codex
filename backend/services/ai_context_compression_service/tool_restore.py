"""
Tool-call history restoration for AI context compression.

Converts the DB storage format (tool_calls_log: [{tool, args, result}]) back into
standard LLM API messages so the model retains full tool-call context across turns.
Supports both OpenAI (tool_calls + tool role) and Anthropic (tool_use/tool_result
content blocks) formats, including DeepSeek reasoning-content quirks.
"""
import json
from typing import Any, Dict, List


def restore_tool_calls_to_messages(
    history: List[Dict[str, Any]],
    api_format: str = "openai",
    model: str = ""
) -> List[Dict[str, Any]]:
    """
    Restore tool_calls_log from DB storage format into standard LLM API messages.

    WHY THIS EXISTS:
    During a single task, the LLM sees full tool_call + tool_result messages in memory.
    But when the task completes, only `content` and `tool_calls_log` (JSON) are saved to DB.
    On the next turn, if we only load `content`, the LLM loses all tool call context and
    may redundantly re-call the same tools. This function restores that context.

    DB storage format (tool_calls_log):
        [{"tool": "get_positions", "args": {"symbol": "BTC"}, "result": "{...}"}]

    Restored to OpenAI format:
        assistant(content="", tool_calls=[...]) -> tool(content="...") -> ... -> assistant(content="final reply")

    Restored to Anthropic format:
        assistant(content=[tool_use blocks]) -> user(content=[tool_result blocks]) -> assistant(content="final reply")

    Args:
        history: List of DB message dicts with keys: role, content, tool_calls_log (optional)
        api_format: "openai" or "anthropic"
        model: Model name, used to apply provider-specific quirks

    Returns:
        List of standard LLM API messages with tool calls properly structured
    """
    messages = []

    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "") or ""
        tool_calls_log_raw = msg.get("tool_calls_log")
        reasoning_snapshot = msg.get("reasoning_snapshot") or ""

        # Parse tool_calls_log (could be JSON string or already a list)
        tool_calls_log = None
        if tool_calls_log_raw:
            if isinstance(tool_calls_log_raw, str):
                try:
                    tool_calls_log = json.loads(tool_calls_log_raw)
                except (json.JSONDecodeError, TypeError):
                    tool_calls_log = None
            elif isinstance(tool_calls_log_raw, list):
                tool_calls_log = tool_calls_log_raw

        # No tool calls -> simple message
        if role != "assistant" or not tool_calls_log:
            if role == "assistant" and api_format == "anthropic":
                from services.ai_decision_service import requires_deepseek_reasoning_content
                if requires_deepseek_reasoning_content(model):
                    blocks = [{
                        "type": "thinking",
                        "thinking": reasoning_snapshot.strip(),
                        "signature": "restored"
                    }]
                    if content:
                        blocks.append({"type": "text", "text": content})
                    messages.append({"role": role, "content": blocks})
                    continue
            messages.append({"role": role, "content": content})
            continue

        # Restore tool calls based on API format
        if api_format == "anthropic":
            messages.extend(
                _restore_anthropic_tool_calls(tool_calls_log, content, model, reasoning_snapshot)
            )
        else:
            messages.extend(
                _restore_openai_tool_calls(tool_calls_log, content, model, reasoning_snapshot)
            )

    return messages


def _restore_openai_tool_calls(
    tool_calls_log: List[Dict[str, Any]],
    final_content: str,
    model: str = "",
    reasoning_snapshot: str = ""
) -> List[Dict[str, Any]]:
    """
    Restore tool calls into OpenAI chat completion format.

    Produces:
      1. assistant message with tool_calls array
      2. One tool message per call with matching tool_call_id
      3. Final assistant message with the actual reply content
    """
    result = []

    # Build assistant message with tool_calls
    tc_array = []
    for i, entry in enumerate(tool_calls_log):
        tc_array.append({
            "id": f"call_restored_{i}",
            "type": "function",
            "function": {
                "name": entry.get("tool", "unknown"),
                "arguments": json.dumps(entry.get("args", {}))
            }
        })

    assistant_msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": tc_array
    }
    # DeepSeek V4 thinking mode requires reasoning_content on tool_call messages.
    from services.ai_decision_service import requires_deepseek_reasoning_content
    if requires_deepseek_reasoning_content(model):
        reasoning_parts = []
        for entry in tool_calls_log:
            for key in ("reasoning_content", "reasoning"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    reasoning_parts.append(value.strip())
                    break
        restored_reasoning = "\n\n".join(reasoning_parts) if reasoning_parts else reasoning_snapshot.strip()
        assistant_msg["reasoning_content"] = restored_reasoning
    result.append(assistant_msg)

    # Add tool result messages
    for i, entry in enumerate(tool_calls_log):
        raw_result = entry.get("result", "")
        result.append({
            "role": "tool",
            "tool_call_id": f"call_restored_{i}",
            "content": raw_result if isinstance(raw_result, str) else json.dumps(raw_result)
        })

    # Final assistant reply
    if final_content:
        final_msg = {"role": "assistant", "content": final_content}
        from services.ai_decision_service import requires_deepseek_reasoning_content
        if requires_deepseek_reasoning_content(model):
            final_msg["reasoning_content"] = ""
        result.append(final_msg)

    return result


def _restore_anthropic_tool_calls(
    tool_calls_log: List[Dict[str, Any]],
    final_content: str,
    model: str = "",
    reasoning_snapshot: str = ""
) -> List[Dict[str, Any]]:
    """
    Restore tool calls into Anthropic messages API format.

    Produces:
      1. assistant message with tool_use content blocks
      2. user message with tool_result content blocks
      3. Final assistant message with the actual reply content
    """
    result = []

    # Build tool_use blocks
    tool_use_blocks = []
    from services.ai_decision_service import requires_deepseek_reasoning_content
    if requires_deepseek_reasoning_content(model):
        reasoning_parts = []
        for entry in tool_calls_log:
            for key in ("thinking", "reasoning_content", "reasoning"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    reasoning_parts.append(value.strip())
                    break
        restored_thinking = "\n\n".join(reasoning_parts) if reasoning_parts else reasoning_snapshot.strip()
        tool_use_blocks.append({
            "type": "thinking",
            "thinking": restored_thinking,
            "signature": "restored"
        })
    for i, entry in enumerate(tool_calls_log):
        tool_use_blocks.append({
            "type": "tool_use",
            "id": f"tooluse_restored_{i}",
            "name": entry.get("tool", "unknown"),
            "input": entry.get("args", {})
        })

    result.append({"role": "assistant", "content": tool_use_blocks})

    # Build tool_result blocks
    tool_result_blocks = []
    for i, entry in enumerate(tool_calls_log):
        raw_result = entry.get("result", "")
        tool_result_blocks.append({
            "type": "tool_result",
            "tool_use_id": f"tooluse_restored_{i}",
            "content": raw_result if isinstance(raw_result, str) else json.dumps(raw_result)
        })

    result.append({"role": "user", "content": tool_result_blocks})

    # Final assistant reply
    if final_content:
        if requires_deepseek_reasoning_content(model):
            result.append({
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "",
                        "signature": "restored"
                    },
                    {"type": "text", "text": final_content}
                ]
            })
        else:
            result.append({"role": "assistant", "content": final_content})

    return result
