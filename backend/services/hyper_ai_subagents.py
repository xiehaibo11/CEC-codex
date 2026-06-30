"""
Hyper AI Sub-agents - Tools for calling specialized AI assistants

Each sub-agent reuses existing AI assistant's conversation system:
- call_prompt_ai: Prompt AI for trading prompt generation/optimization
- call_program_ai: Program AI for strategy code writing
- call_signal_ai: Signal AI for signal pool configuration
- call_attribution_ai: Attribution AI for trade analysis

Sub-agents maintain their own conversation history in their respective tables.
Hyper AI passes conversation_id to continue previous sessions.

ARCHITECTURE NOTE: Sub-agent execution returns a Generator, not a string.
The generator yields subagent_progress SSE events (forwarded to frontend via
StreamBufferManager for real-time progress display), and finally yields a
subagent_result event containing the final JSON string for the main LLM.
See ai_stream_service.py module docstring for the full buffer/polling architecture.
"""

import json
import logging
import os
from typing import Any, Dict, Generator, Optional

from sqlalchemy.orm import Session

__path__ = [os.path.join(os.path.dirname(__file__), "hyper_ai_subagents")]

from services.hyper_ai_subagents.dispatch import (  # noqa: E402
    SUBAGENT_DISPATCH_MAP,
    build_dispatch_kwargs,
)
from services.hyper_ai_subagents.requests import (  # noqa: E402
    build_attribution_ai_request,
    build_program_ai_request,
    build_prompt_ai_request,
    build_signal_ai_request,
)
from services.hyper_ai_subagents.streaming import (  # noqa: E402
    SUBAGENT_DISPLAY_NAMES,
    _run_subagent_stream,
)
from services.hyper_ai_subagents.tools import SUBAGENT_TOOLS  # noqa: E402


logger = logging.getLogger(__name__)


def execute_call_prompt_ai(
    db: Session,
    task: str,
    conversation_id: Optional[int] = None,
    prompt_id: Optional[int] = None,
    user_id: int = 1
) -> Generator[str, None, str]:
    """
    Execute Prompt AI sub-agent. Returns a generator that yields progress
    SSE events and finally returns the result JSON string via StopIteration.value.
    """
    from services.ai_prompt_generation_service import generate_prompt_with_ai_stream
    from services.hyper_ai_service import get_llm_config

    logger.info(f"[call_prompt_ai] task={task[:50]}..., conv_id={conversation_id}, prompt_id={prompt_id}")

    try:
        llm_config = get_llm_config(db)
        if not llm_config.get("configured"):
            return json.dumps({
                "subagent": "prompt_ai",
                "status": "failed",
                "error": "Hyper AI LLM not configured."
            })

        generator = generate_prompt_with_ai_stream(
            **build_prompt_ai_request(
                db=db,
                task=task,
                conversation_id=conversation_id,
                prompt_id=prompt_id,
                user_id=user_id,
                llm_config=llm_config,
            )
        )

        result = yield from _run_subagent_stream(generator, "call_prompt_ai")

        return json.dumps({
            "subagent": "prompt_ai",
            "status": result["status"],
            "conversation_id": result["conversation_id"],
            "message_id": result["message_id"],
            "content": result["content"],
            "tool_calls_count": len(result["tool_calls"]),
            "error": result["error"]
        })

    except Exception as e:
        logger.error(f"[call_prompt_ai] Error: {e}")
        return json.dumps({"subagent": "prompt_ai", "status": "failed", "error": str(e)})


def execute_call_program_ai(
    db: Session,
    task: str,
    conversation_id: Optional[int] = None,
    program_id: Optional[int] = None,
    user_id: int = 1
) -> Generator[str, None, str]:
    """Execute Program AI sub-agent. Yields progress events, returns result JSON."""
    from services.ai_program_service import generate_program_with_ai_stream
    from services.hyper_ai_service import get_llm_config

    logger.info(f"[call_program_ai] task={task[:50]}..., conv_id={conversation_id}")

    try:
        llm_config = get_llm_config(db)
        if not llm_config.get("configured"):
            return json.dumps({
                "subagent": "program_ai",
                "status": "failed",
                "error": "Hyper AI LLM not configured."
            })

        generator = generate_program_with_ai_stream(
            **build_program_ai_request(
                db=db,
                task=task,
                conversation_id=conversation_id,
                program_id=program_id,
                user_id=user_id,
                llm_config=llm_config,
            )
        )

        result = yield from _run_subagent_stream(generator, "call_program_ai")

        return json.dumps({
            "subagent": "program_ai",
            "status": result["status"],
            "conversation_id": result["conversation_id"],
            "message_id": result["message_id"],
            "content": result["content"],
            "tool_calls_count": len(result["tool_calls"]),
            "error": result["error"]
        })

    except Exception as e:
        logger.error(f"[call_program_ai] Error: {e}")
        return json.dumps({"subagent": "program_ai", "status": "failed", "error": str(e)})


def execute_call_signal_ai(
    db: Session,
    task: str,
    conversation_id: Optional[int] = None,
    user_id: int = 1
) -> Generator[str, None, str]:
    """Execute Signal AI sub-agent. Yields progress events, returns result JSON."""
    from services.ai_signal_generation_service import generate_signal_with_ai_stream
    from services.hyper_ai_service import get_llm_config

    logger.info(f"[call_signal_ai] task={task[:50]}..., conv_id={conversation_id}")

    try:
        llm_config = get_llm_config(db)
        if not llm_config.get("configured"):
            return json.dumps({
                "subagent": "signal_ai",
                "status": "failed",
                "error": "Hyper AI LLM not configured."
            })

        generator = generate_signal_with_ai_stream(
            **build_signal_ai_request(
                db=db,
                task=task,
                conversation_id=conversation_id,
                user_id=user_id,
                llm_config=llm_config,
            )
        )

        result = yield from _run_subagent_stream(generator, "call_signal_ai")

        return json.dumps({
            "subagent": "signal_ai",
            "status": result["status"],
            "conversation_id": result["conversation_id"],
            "message_id": result["message_id"],
            "content": result["content"],
            "tool_calls_count": len(result["tool_calls"]),
            "error": result["error"]
        })

    except Exception as e:
        logger.error(f"[call_signal_ai] Error: {e}")
        return json.dumps({"subagent": "signal_ai", "status": "failed", "error": str(e)})


def execute_call_attribution_ai(
    db: Session,
    task: str,
    conversation_id: Optional[int] = None,
    user_id: int = 1
) -> Generator[str, None, str]:
    """Execute Attribution AI sub-agent. Yields progress events, returns result JSON."""
    from services.ai_attribution_service import generate_attribution_analysis_stream
    from services.hyper_ai_service import get_llm_config

    logger.info(f"[call_attribution_ai] task={task[:50]}..., conv_id={conversation_id}")

    try:
        llm_config = get_llm_config(db)
        if not llm_config.get("configured"):
            return json.dumps({
                "subagent": "attribution_ai",
                "status": "failed",
                "error": "Hyper AI LLM not configured."
            })

        generator = generate_attribution_analysis_stream(
            **build_attribution_ai_request(
                db=db,
                task=task,
                conversation_id=conversation_id,
                user_id=user_id,
                llm_config=llm_config,
            )
        )

        result = yield from _run_subagent_stream(generator, "call_attribution_ai")

        return json.dumps({
            "subagent": "attribution_ai",
            "status": result["status"],
            "conversation_id": result["conversation_id"],
            "message_id": result["message_id"],
            "content": result["content"],
            "tool_calls_count": len(result["tool_calls"]),
            "error": result["error"]
        })

    except Exception as e:
        logger.error(f"[call_attribution_ai] Error: {e}")
        return json.dumps({"subagent": "attribution_ai", "status": "failed", "error": str(e)})


def execute_subagent_tool(
    db: Session,
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: int = 1
) -> Generator[str, None, str]:
    """
    Execute a sub-agent tool by name. Returns a generator that yields
    subagent_progress SSE events and returns the final result JSON string.

    The caller in hyper_ai_service.py uses:
        gen = execute_subagent_tool(db, name, args)
        tool_result = yield from gen  # forwards progress events, gets result
    """
    try:
        dispatch_kwargs = build_dispatch_kwargs(tool_name, arguments, user_id)
        if dispatch_kwargs is None:
            return json.dumps({"error": f"Unknown sub-agent tool: {tool_name}"})

        executor_name = SUBAGENT_DISPATCH_MAP[tool_name].executor_name
        executor = globals()[executor_name]
        return (yield from executor(db, **dispatch_kwargs))

    except Exception as e:
        logger.error(f"[execute_subagent_tool] Error executing {tool_name}: {e}")
        return json.dumps({"error": str(e)})
