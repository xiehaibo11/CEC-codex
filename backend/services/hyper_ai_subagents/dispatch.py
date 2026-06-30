"""Dispatch metadata for Hyper AI sub-agent tools."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SubagentDispatchSpec:
    executor_name: str
    extra_argument_names: tuple[str, ...] = ()


SUBAGENT_DISPATCH_MAP = {
    "call_prompt_ai": SubagentDispatchSpec(
        executor_name="execute_call_prompt_ai",
        extra_argument_names=("prompt_id",),
    ),
    "call_program_ai": SubagentDispatchSpec(
        executor_name="execute_call_program_ai",
        extra_argument_names=("program_id",),
    ),
    "call_signal_ai": SubagentDispatchSpec(
        executor_name="execute_call_signal_ai",
    ),
    "call_attribution_ai": SubagentDispatchSpec(
        executor_name="execute_call_attribution_ai",
    ),
}


def build_dispatch_kwargs(
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: int,
) -> Optional[Dict[str, Any]]:
    spec = SUBAGENT_DISPATCH_MAP.get(tool_name)
    if spec is None:
        return None

    kwargs: Dict[str, Any] = {
        "task": arguments.get("task", ""),
        "conversation_id": arguments.get("conversation_id"),
        "user_id": user_id,
    }
    for argument_name in spec.extra_argument_names:
        kwargs[argument_name] = arguments.get(argument_name)
    return kwargs
