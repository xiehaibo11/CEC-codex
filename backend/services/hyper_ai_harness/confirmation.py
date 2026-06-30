import json
import re
import time
import uuid
from typing import Any, Dict

from services.hyper_ai_harness.types import TOOL_STATUS_BLOCKED, ToolExecutionMeta


SENSITIVE_ARG_PATTERNS = re.compile(r"(api[_-]?key|secret|token|private|password)", re.IGNORECASE)


def _mask_value(key: str, value: Any) -> Any:
    if SENSITIVE_ARG_PATTERNS.search(key):
        return "***"
    if isinstance(value, dict):
        return {k: _mask_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(key, item) for item in value[:10]]
    return value


def mask_tool_args(arguments: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _mask_value(key, value) for key, value in (arguments or {}).items()}


def build_confirmation_description(tool_name: str, arguments: Dict[str, Any]) -> str:
    args = mask_tool_args(arguments or {})
    labels = {
        "bind_prompt_to_trader": "Bind a prompt template to an AI Trader",
        "bind_program_to_trader": "Bind a trading program to an AI Trader",
        "update_trader_strategy": "Update an AI Trader trigger strategy",
        "update_ai_trader": "Update an AI Trader configuration",
        "update_program_binding": "Update a program binding",
        "update_prompt_binding": "Update a prompt binding",
        "delete_trader": "Delete an AI Trader",
        "delete_prompt_template": "Delete a prompt template",
        "delete_signal_definition": "Delete a signal definition",
        "delete_signal_pool": "Delete a signal pool",
        "delete_trading_program": "Delete a trading program",
        "delete_prompt_binding": "Delete a prompt binding",
        "delete_program_binding": "Delete a program binding",
        "save_prompt": "Update a prompt that is already used by an active trader",
        "save_program": "Update a program that is already used by an active trader",
        "update_signal_pool": "Update a signal pool used by an active trader",
    }
    summary = json.dumps(args, ensure_ascii=False)
    if len(summary) > 600:
        summary = summary[:600] + "...[truncated]"
    return f"{labels.get(tool_name, tool_name)} with arguments: {summary}"


def generate_confirmation_id() -> str:
    return f"confirm_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def blocked_tool_result(message: str) -> str:
    return json.dumps({
        "status": "blocked",
        "message": message,
        "executed": False,
    }, ensure_ascii=False)


def blocked_meta(tool_name: str, message: str) -> ToolExecutionMeta:
    return ToolExecutionMeta(
        tool_name=tool_name,
        status=TOOL_STATUS_BLOCKED,
        code="confirmation_required",
        message=message,
        retryable=False,
    )


def circuit_breaker_result(tool_name: str) -> str:
    return json.dumps({
        "status": "blocked",
        "message": f"Tool {tool_name} is temporarily unavailable after repeated infrastructure failures. Use another path or ask the user to retry later.",
        "executed": False,
    }, ensure_ascii=False)
