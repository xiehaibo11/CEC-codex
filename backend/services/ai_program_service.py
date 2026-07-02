"""Compatibility entry point for AI program generation services."""
from services.ai_program_generation_backtest_tools import (
    _get_backtest_history,
    _get_trigger_details,
    _get_trigger_list,
    _quick_verify_strategy,
)
from services.ai_program_generation_config import (
    BACKTEST_ANALYSIS_TOOLS,
    DECISION_API_DOCS,
    FACTOR_QUERY_TOOL,
    MARKET_API_DOCS,
    PROGRAM_SYSTEM_PROMPT,
    PROGRAM_TOOLS,
    PROGRAM_TOOLS_ANTHROPIC,
)
from services.ai_program_generation_core import (
    API_BASE_DELAY,
    API_MAX_DELAY,
    API_MAX_RETRIES,
    RETRYABLE_STATUS_CODES,
    _call_anthropic_streaming,
    _get_retry_delay,
    _should_retry_api,
)
from services.ai_program_generation_execution_tools import (
    _execute_tool,
    _format_tool_calls_log,
    _test_run_code,
    _validate_python_code,
)
from services.ai_program_generation_market_tools import _query_market_data
from services.ai_program_generation_stream import generate_program_with_ai_stream

__all__ = [
    "API_MAX_RETRIES",
    "API_BASE_DELAY",
    "API_MAX_DELAY",
    "RETRYABLE_STATUS_CODES",
    "PROGRAM_SYSTEM_PROMPT",
    "PROGRAM_TOOLS",
    "BACKTEST_ANALYSIS_TOOLS",
    "FACTOR_QUERY_TOOL",
    "PROGRAM_TOOLS_ANTHROPIC",
    "MARKET_API_DOCS",
    "DECISION_API_DOCS",
    "_should_retry_api",
    "_get_retry_delay",
    "_call_anthropic_streaming",
    "_query_market_data",
    "_get_backtest_history",
    "_get_trigger_list",
    "_get_trigger_details",
    "_quick_verify_strategy",
    "_execute_tool",
    "_format_tool_calls_log",
    "_validate_python_code",
    "_test_run_code",
    "generate_program_with_ai_stream",
]
