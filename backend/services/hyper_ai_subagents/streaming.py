"""Streaming helpers for Hyper AI sub-agent execution."""

import json
import logging
from typing import Any, Dict, Generator

from services.ai_stream_service import format_sse_event


logger = logging.getLogger(__name__)


# Human-readable names for sub-agents (used in progress events sent to frontend).
SUBAGENT_DISPLAY_NAMES = {
    "call_prompt_ai": "Prompt AI",
    "call_program_ai": "Program AI",
    "call_signal_ai": "Signal AI",
    "call_attribution_ai": "Attribution AI",
}


def _run_subagent_stream(
    generator,
    subagent_name: str = "sub-agent",
) -> Generator[str, None, Dict[str, Any]]:
    """
    Run a sub-agent's streaming generator, yield progress events, and collect results.

    This is a GENERATOR that:
    1. Consumes the sub-agent's SSE stream event by event
    2. Yields subagent_progress SSE events for each meaningful step (tool_call, tool_round)
       - These events flow up through the main chat generator -> StreamBufferManager -> frontend
    3. Collects the final result internally (same as before)
    4. Returns the result dict via generator return value (accessed via StopIteration.value)

    The caller uses: result = yield from _run_subagent_stream(gen, name)
    """
    display_name = SUBAGENT_DISPLAY_NAMES.get(subagent_name, subagent_name)
    result = {
        "status": "failed",
        "content": "",
        "conversation_id": None,
        "message_id": None,
        "tool_calls": [],
        "error": None,
    }

    try:
        for event_str in generator:
            # Skip empty strings.
            if not event_str or not event_str.strip():
                continue

            event_type = None
            event_data = None

            # Check if this is standard SSE format: "event: xxx\ndata: {...}\n\n".
            if event_str.startswith("event: "):
                lines = event_str.strip().split("\n")
                for line in lines:
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:].strip())
                        except json.JSONDecodeError:
                            continue
            elif event_str.startswith("data: "):
                try:
                    event_data = json.loads(event_str[6:].strip())
                    event_type = event_data.get("type")
                except json.JSONDecodeError:
                    continue

            # Skip if we couldn't parse.
            if not event_type or event_data is None:
                continue

            if event_type == "conversation_created":
                result["conversation_id"] = event_data.get("conversation_id")

            elif event_type == "reasoning":
                reasoning_text = event_data.get("content", "")
                if reasoning_text:
                    yield format_sse_event(
                        "subagent_progress",
                        {
                            "subagent": display_name,
                            "step": "reasoning",
                            "content": reasoning_text[:200],
                        },
                    )

            elif event_type == "tool_call":
                tool_name = event_data.get("name", "")
                result["tool_calls"].append(
                    {
                        "name": tool_name,
                        "args": event_data.get("args") or event_data.get("arguments"),
                    }
                )
                yield format_sse_event(
                    "subagent_progress",
                    {
                        "subagent": display_name,
                        "step": "tool_call",
                        "tool": tool_name,
                        "tool_calls_count": len(result["tool_calls"]),
                    },
                )

            elif event_type == "tool_result":
                tool_name = event_data.get("name", "")
                yield format_sse_event(
                    "subagent_progress",
                    {
                        "subagent": display_name,
                        "step": "tool_result",
                        "tool": tool_name,
                    },
                )

            elif event_type == "tool_round":
                yield format_sse_event(
                    "subagent_progress",
                    {
                        "subagent": display_name,
                        "step": "tool_round",
                        "round": event_data.get("round"),
                        "max_rounds": event_data.get("max_rounds")
                        or event_data.get("max"),
                    },
                )

            elif event_type == "content":
                result["content"] += event_data.get("content", "")

            elif event_type == "done":
                result["status"] = "success"
                result["content"] = event_data.get("content", result["content"])
                result["conversation_id"] = event_data.get(
                    "conversation_id",
                    result["conversation_id"],
                )
                result["message_id"] = event_data.get("message_id")
                break

            elif event_type == "error":
                result["status"] = "failed"
                result["error"] = event_data.get("content") or event_data.get(
                    "message",
                    "Unknown error",
                )
                break

            elif event_type == "interrupted":
                result["status"] = "interrupted"
                result["error"] = event_data.get("error", "Interrupted")
                result["message_id"] = event_data.get("message_id")
                break

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        logger.error(f"[_run_subagent_stream] Error: {e}")

    return result
