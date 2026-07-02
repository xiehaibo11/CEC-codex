"""Compatibility entry point for AI signal generation services."""
from services.ai_signal_generation_config import SIGNAL_SYSTEM_PROMPT, SIGNAL_TOOLS
from services.ai_signal_generation_history import (
    get_signal_conversation_history,
    get_signal_conversation_messages,
)
from services.ai_signal_generation_parser import (
    extract_signal_configs,
    _extract_balanced_json,
    _try_parse_signal_json,
)
from services.ai_signal_generation_stream import generate_signal_with_ai_stream
from services.ai_signal_generation_sync import generate_signal_with_ai
from services.ai_signal_generation_tool_market import (
    _tool_backtest_threshold,
    _tool_get_indicator_statistics,
    _tool_get_indicators_batch,
    _tool_get_kline_context,
)
from services.ai_signal_generation_tool_prediction import (
    _combine_signals_with_pool_edge_detection,
    _execute_tool,
    _format_tool_calls_log,
    _sse_event,
    _tool_predict_signal_combination,
)
from services.ai_signal_generation_tool_triggers import (
    _find_factor_signal_triggers,
    _find_taker_volume_triggers,
    _find_triggers_with_preloaded_data,
)

__all__ = [
    "SIGNAL_SYSTEM_PROMPT",
    "SIGNAL_TOOLS",
    "generate_signal_with_ai",
    "generate_signal_with_ai_stream",
    "extract_signal_configs",
    "get_signal_conversation_history",
    "get_signal_conversation_messages",
    "_extract_balanced_json",
    "_try_parse_signal_json",
    "_tool_get_indicator_statistics",
    "_tool_backtest_threshold",
    "_tool_get_kline_context",
    "_tool_get_indicators_batch",
    "_combine_signals_with_pool_edge_detection",
    "_tool_predict_signal_combination",
    "_find_factor_signal_triggers",
    "_find_triggers_with_preloaded_data",
    "_find_taker_volume_triggers",
    "_execute_tool",
    "_sse_event",
    "_format_tool_calls_log",
]
