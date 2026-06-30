"""
AI Attribution Analysis Service

Handles AI-assisted attribution analysis conversations using LLM.
Supports Function Calling for AI to query trading performance data.
Role: Strategy Diagnosis Doctor - analyze performance, identify issues, suggest improvements.

This module is split by responsibility into the `ai_attribution_service/` package:
- prompts: ATTRIBUTION_SYSTEM_PROMPT
- tools_schema: ATTRIBUTION_TOOLS + _define_tools
- tools: tool implementations (_execute_tool, _tool_*, _get_fees_for_decisions)
- stream: streaming analysis loop + conversation/message retrieval

The names below remain importable from this path to preserve the public API.
"""
import os

__path__ = [os.path.join(os.path.dirname(__file__), "ai_attribution_service")]

from services.ai_attribution_service.prompts import (  # noqa: E402,F401
    ATTRIBUTION_SYSTEM_PROMPT,
)
from services.ai_attribution_service.tools_schema import (  # noqa: E402,F401
    ATTRIBUTION_TOOLS,
    _define_tools,
)
from services.ai_attribution_service.tools import (  # noqa: E402,F401
    _execute_tool,
    _get_fees_for_decisions,
    _tool_get_account_strategy,
    _tool_get_attribution_summary,
    _tool_get_factor_attribution,
    _tool_get_prompt_template,
    _tool_get_signal_pool_config,
    _tool_get_trade_decision_chain,
    _tool_list_ai_accounts,
    _tool_suggest_prompt_modification,
)
from services.ai_attribution_service.stream import (  # noqa: E402,F401
    extract_diagnosis_results,
    generate_attribution_analysis_stream,
    get_attribution_conversations,
    get_attribution_messages,
)
