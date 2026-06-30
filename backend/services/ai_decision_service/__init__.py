"""
AI Decision Service - Handles AI model API calls for trading decisions.

This package preserves the historical ``services.ai_decision_service`` import
surface. The implementation is split by responsibility across submodules:

- ``constants``           - static config, SafeDict, output-format/decision text
- ``prompt_formatting``   - portfolio/market/sampling text formatting helpers
- ``llm_models``          - model capability detection, token sizing, API format
- ``llm_payload``         - payload/headers builders, message/response parsing
- ``indicator_formatting``- technical indicator and flow value formatting
- ``kline_context``       - K-line / factor template variable parsing & context
- ``prompt_context``      - prompt context assembly (single source of truth)
- ``persistence``         - decision persistence and active-account selection
- ``decision_engine``     - call_ai_for_decision orchestration

Every public (and previously importable) name remains exported from this path.
"""
from services.ai_decision_service.constants import (
    DECISION_TASK_TEXT,
    DEMO_API_KEYS,
    MAX_LEVERAGE_PLACEHOLDER,
    OUTPUT_FORMAT_COMPLETE,
    OUTPUT_FORMAT_JSON,
    SUPPORTED_SYMBOLS,
    SYMBOL_PLACEHOLDER,
    SafeDict,
)
from services.ai_decision_service.prompt_formatting import (
    _build_account_state,
    _build_holdings_detail,
    _build_market_prices,
    _build_market_snapshot,
    _build_multi_symbol_sampling_data,
    _build_sampling_data,
    _build_session_context,
    _calculate_runtime_minutes,
    _calculate_total_return_percent,
    _format_currency,
    _format_market_data_block,
    _format_quantity,
    _get_metric_unit,
    _get_realtime_ticker_snapshot,
    _normalize_symbol_metadata,
)
from services.ai_decision_service.llm_models import (
    DEEPSEEK_REASONING_CONTENT_MODEL_MARKERS,
    NEW_MODEL_MARKERS,
    REASONING_MODEL_MARKERS,
    build_chat_completion_endpoints,
    detect_api_format,
    get_max_tokens,
    is_minimax_anthropic_url,
    is_new_openai_model,
    is_reasoning_model,
    requires_deepseek_reasoning_content,
)
from services.ai_decision_service.llm_payload import (
    _THINKING_TAG_RE,
    _extract_text_from_message,
    build_llm_headers,
    build_llm_payload,
    convert_messages_to_anthropic,
    convert_tools_to_anthropic,
    extract_reasoning,
    strip_thinking_tags,
)
from services.ai_decision_service.indicator_formatting import (
    _format_flow_indicator,
    _format_price_value,
    _format_single_indicator,
    _format_usd,
)
from services.ai_decision_service.kline_context import (
    _build_factor_context,
    _build_klines_and_indicators_context,
    _parse_factor_variables,
    _parse_kline_indicator_variables,
    _process_single_symbol_period,
)
from services.ai_decision_service.prompt_context import (
    _build_prompt_context,
    _get_portfolio_data,
)
from services.ai_decision_service.persistence import (
    _is_default_api_key,
    get_active_ai_accounts,
    save_ai_decision,
)
from services.ai_decision_service.decision_engine import call_ai_for_decision

__all__ = [
    "DECISION_TASK_TEXT",
    "DEMO_API_KEYS",
    "MAX_LEVERAGE_PLACEHOLDER",
    "OUTPUT_FORMAT_COMPLETE",
    "OUTPUT_FORMAT_JSON",
    "SUPPORTED_SYMBOLS",
    "SYMBOL_PLACEHOLDER",
    "SafeDict",
    "_build_account_state",
    "_build_holdings_detail",
    "_build_market_prices",
    "_build_market_snapshot",
    "_build_multi_symbol_sampling_data",
    "_build_sampling_data",
    "_build_session_context",
    "_calculate_runtime_minutes",
    "_calculate_total_return_percent",
    "_format_currency",
    "_format_market_data_block",
    "_format_quantity",
    "_get_metric_unit",
    "_get_realtime_ticker_snapshot",
    "_normalize_symbol_metadata",
    "DEEPSEEK_REASONING_CONTENT_MODEL_MARKERS",
    "NEW_MODEL_MARKERS",
    "REASONING_MODEL_MARKERS",
    "build_chat_completion_endpoints",
    "detect_api_format",
    "get_max_tokens",
    "is_minimax_anthropic_url",
    "is_new_openai_model",
    "is_reasoning_model",
    "requires_deepseek_reasoning_content",
    "_THINKING_TAG_RE",
    "_extract_text_from_message",
    "build_llm_headers",
    "build_llm_payload",
    "convert_messages_to_anthropic",
    "convert_tools_to_anthropic",
    "extract_reasoning",
    "strip_thinking_tags",
    "_format_flow_indicator",
    "_format_price_value",
    "_format_single_indicator",
    "_format_usd",
    "_build_factor_context",
    "_build_klines_and_indicators_context",
    "_parse_factor_variables",
    "_parse_kline_indicator_variables",
    "_process_single_symbol_period",
    "_build_prompt_context",
    "_get_portfolio_data",
    "_is_default_api_key",
    "get_active_ai_accounts",
    "save_ai_decision",
    "call_ai_for_decision",
]
