"""Harnessed tool execution and the high-risk confirmation gate for Hyper AI.

Wraps every tool call from the streaming loop with runtime guardrails:
circuit-breaker checks, risk assessment, the user-confirmation pause for
high-risk writes, sub-agent contract checks, and tool_error SSE events.
"""
import logging
from typing import Any, Dict, Generator, Optional

from sqlalchemy.orm import Session

from database.models import HyperAiMessage
from services.ai_stream_service import (
    get_buffer_manager,
    format_sse_event,
)
from services.hyper_ai_subagents import execute_subagent_tool
from services.hyper_ai_harness import (
    RISK_HIGH,
    TOOL_STATUS_BLOCKED,
    TOOL_STATUS_DOMAIN_ERROR,
    TOOL_STATUS_INFRA_ERROR,
    TOOL_STATUS_WARNING,
    SubAgentContractChecker,
    ToolFailureTracker,
    assess_tool_risk,
    blocked_meta,
    blocked_tool_result,
    circuit_breaker_result,
    execute_tool_with_meta,
    generate_confirmation_id,
    mask_tool_args,
)

logger = logging.getLogger(__name__)


# Sub-agent tool names — these return generators instead of strings
SUBAGENT_TOOL_NAMES = {"call_prompt_ai", "call_program_ai", "call_signal_ai", "call_attribution_ai"}


# Sub-agent tools are executed via execute_subagent_tool (generator, yields progress events).
# Normal tools are executed via execute_hyper_ai_tool (plain function, returns string).
# These two paths MUST stay separate - never wrap them in a single function that contains
# both yield and return, because Python turns ANY function with yield into a generator.


def _tool_error_event_data(meta, severity: str = None) -> Dict[str, Any]:
    return {
        "name": meta.tool_name,
        "status": meta.status,
        "severity": severity or meta.status,
        "code": meta.code,
        "message": meta.message,
        "retryable": meta.retryable,
    }


def _await_tool_confirmation(
    db: Session,
    assistant_msg: HyperAiMessage,
    task_id: Optional[str],
    fn_name: str,
    fn_args: Dict[str, Any],
    risk_assessment,
) -> Generator[str, None, tuple[bool, str]]:
    """Pause a high-risk tool call until the user confirms it."""
    if risk_assessment.risk_level != RISK_HIGH:
        return True, ""

    if not task_id:
        return False, blocked_tool_result(
            "High-risk operation was blocked because the streaming task ID is missing."
        )

    manager = get_buffer_manager()
    confirmation_id = generate_confirmation_id()
    if not manager.begin_confirmation(task_id, confirmation_id):
        return False, blocked_tool_result(
            "High-risk operation was blocked because another confirmation is pending or the task is no longer running."
        )

    assistant_msg.content = "[Waiting for user confirmation...]"
    db.commit()

    yield format_sse_event("confirmation_required", {
        "tool_name": fn_name,
        "args": mask_tool_args(fn_args),
        "description": risk_assessment.description,
        "reason": risk_assessment.reason,
        "confirmation_id": confirmation_id,
    })

    task = manager.get_task(task_id)
    if not task:
        manager.clear_confirmation(task_id, confirmation_id)
        return False, blocked_tool_result("High-risk operation was blocked because the task is no longer available.")

    try:
        confirmed = task.confirmation_event.wait(timeout=300)
        response = task.confirmation_response
    finally:
        manager.clear_confirmation(task_id, confirmation_id)

    if not confirmed or not response or not response.get("confirmed"):
        return False, blocked_tool_result(
            "User declined this operation. The tool was NOT executed. "
            "Do NOT retry or re-ask. Simply acknowledge the cancellation and move on."
        )

    return True, ""


def _execute_harnessed_tool_call(
    db: Session,
    assistant_msg: HyperAiMessage,
    task_id: Optional[str],
    fn_name: str,
    fn_args: Dict[str, Any],
    failure_tracker: ToolFailureTracker,
    llm_config: Dict[str, Any],
) -> Generator[str, None, str]:
    """Execute a Hyper AI tool with runtime harness guardrails."""
    if failure_tracker.is_tripped(fn_name):
        tool_result = circuit_breaker_result(fn_name)
        meta = blocked_meta(fn_name, "Tool is temporarily unavailable after repeated infrastructure failures.")
        yield format_sse_event("tool_error", _tool_error_event_data(meta, severity="circuit_breaker"))
        return tool_result

    risk_assessment = assess_tool_risk(db, fn_name, fn_args)
    confirmed, blocked_result = yield from _await_tool_confirmation(
        db=db,
        assistant_msg=assistant_msg,
        task_id=task_id,
        fn_name=fn_name,
        fn_args=fn_args,
        risk_assessment=risk_assessment,
    )
    if not confirmed:
        meta = blocked_meta(fn_name, "User confirmation was not received. The tool was not executed.")
        yield format_sse_event("tool_error", _tool_error_event_data(meta, severity="user_cancelled"))
        return blocked_result

    if fn_name in SUBAGENT_TOOL_NAMES:
        tool_result = yield from execute_subagent_tool(db, fn_name, fn_args, user_id=1)
        contract_ok, warning = SubAgentContractChecker.check(fn_name, tool_result)
        if not contract_ok:
            tool_result = f"{warning}\n{tool_result}"
            meta = blocked_meta(fn_name, warning)
            meta.status = TOOL_STATUS_DOMAIN_ERROR
            meta.code = "contract_fail"
            yield format_sse_event("tool_error", _tool_error_event_data(meta, severity="contract_fail"))
        return tool_result

    tool_result, meta = execute_tool_with_meta(
        db,
        fn_name,
        fn_args,
        user_id=1,
        api_config=llm_config,
    )
    failure_tracker.record(meta)

    if meta.status in (TOOL_STATUS_INFRA_ERROR, TOOL_STATUS_BLOCKED, TOOL_STATUS_WARNING):
        severity = "infra_error" if meta.status == TOOL_STATUS_INFRA_ERROR else meta.status
        data = _tool_error_event_data(meta, severity=severity)
        if meta.status == TOOL_STATUS_INFRA_ERROR:
            data["failure_count"] = failure_tracker.failure_count(fn_name)
            data["circuit_breaker_tripped"] = failure_tracker.is_tripped(fn_name)
        yield format_sse_event("tool_error", data)

    return tool_result
