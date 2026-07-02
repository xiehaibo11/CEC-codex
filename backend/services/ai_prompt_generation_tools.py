"""
Tool definitions and execution for AI prompt generation.
"""
import json
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from services.ai_decision_service import convert_tools_to_anthropic
from services.ai_prompt_generation_core import load_variables_reference
from services.ai_prompt_generation_preview import _execute_preview_prompt
from services.ai_prompt_generation_variables import (
    _extract_variables_from_text,
    _validate_variable,
)
from services.ai_prompt_shared_tools import (
    PROMPT_CONTEXT_TOOLS,
    execute_get_prompt_context,
    execute_get_trader_details,
    execute_get_decision_list,
    execute_get_decision_details,
    execute_query_market_data,
)
from services.ai_shared_tools import (
    SHARED_SIGNAL_TOOLS,
    execute_get_signal_pools,
    execute_run_signal_backtest,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Tool Definitions (OpenAI format)
# ============================================================================

PROMPT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_variables_reference",
            "description": "Get the complete list of available variables that can be used in trading prompts. Returns documentation for market data, K-line, technical indicators, flow indicators, position/account variables, etc.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_variables",
            "description": "Validate that all variables used in a prompt text are valid and available. Returns list of valid and invalid variables found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_text": {
                        "type": "string",
                        "description": "The prompt text to validate for variable usage",
                    },
                },
                "required": ["prompt_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_prompt",
            "description": "Preview the prompt with real market data to verify variables work correctly. Returns rendered text and variable status. Note: Account-related variables (equity, positions, trades, trigger_context) will show placeholder values since the prompt is not yet bound to an AI Trader. Market data and technical indicators will show real values.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_text": {
                        "type": "string",
                        "description": "The prompt text to preview",
                    },
                    "asset": {
                        "type": "string",
                        "description": "Primary asset symbol for market data (default: BTC)",
                        "default": "BTC",
                    },
                },
                "required": ["prompt_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_apply_prompt",
            "description": "Suggest applying the generated prompt to a specific AI Trader. Call this when you have a complete, validated prompt ready for the user to apply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_text": {
                        "type": "string",
                        "description": "The complete prompt text to apply",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what this prompt does (1-2 sentences)",
                    },
                },
                "required": ["prompt_text", "summary"],
            },
        },
    },
    # Factor query tool (reused from hyper_ai_tools)
    {
        "type": "function",
        "function": {
            "name": "query_factors",
            "description": "Query factor library and effectiveness data. Without symbol: returns factor list with names (for use in prompt variables like {SYMBOL_factor_PERIOD_NAME}). With symbol: returns factor values and effectiveness ranking. Response includes IC, ICIR, win_rate, decay_half_life_hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exchange": {
                        "type": "string",
                        "enum": ["hyperliquid", "binance"],
                        "description": "Exchange (required)",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol (e.g., BTC). If omitted, returns factor library list.",
                    },
                    "factor_name": {
                        "type": "string",
                        "description": "Specific factor name for detailed info",
                    },
                    "forward_period": {
                        "type": "string",
                        "enum": ["1h", "4h", "12h", "24h"],
                        "description": "Forward period for effectiveness (default: 4h)",
                    },
                },
                "required": ["exchange"],
            },
        },
    },
] + PROMPT_CONTEXT_TOOLS + SHARED_SIGNAL_TOOLS


# Pre-convert tools for Anthropic format
PROMPT_TOOLS_ANTHROPIC = convert_tools_to_anthropic(PROMPT_TOOLS)


# ============================================================================
# Tool Execution Functions
# ============================================================================

def execute_tool(
    tool_name: str,
    args: Dict[str, Any],
    request_id: str,
    db: Session = None,
    prompt_id: int = None,
) -> str:
    """Execute a tool and return the result as a string."""
    logger.info(f"[AI Prompt Gen {request_id}] Executing tool: {tool_name}")

    try:
        if tool_name == "get_variables_reference":
            return load_variables_reference()

        elif tool_name == "validate_variables":
            prompt_text = args.get("prompt_text", "")
            variables = _extract_variables_from_text(prompt_text)

            valid_vars = []
            invalid_vars = []
            for var in variables:
                if _validate_variable(var):
                    valid_vars.append(var)
                else:
                    invalid_vars.append(var)

            result = {
                "total_found": len(variables),
                "valid_count": len(valid_vars),
                "invalid_count": len(invalid_vars),
                "valid_variables": sorted(valid_vars),
                "invalid_variables": sorted(invalid_vars),
            }
            if invalid_vars:
                result["warning"] = f"Found {len(invalid_vars)} invalid variable(s). Please check spelling or refer to variables reference."
            else:
                result["status"] = "All variables are valid."
            return json.dumps(result, indent=2)

        elif tool_name == "preview_prompt":
            return _execute_preview_prompt(args, request_id)

        elif tool_name == "suggest_apply_prompt":
            prompt_text = args.get("prompt_text", "")
            summary = args.get("summary", "")
            # This is a special tool - return structured data for frontend
            return json.dumps({
                "action": "suggest_apply",
                "prompt_text": prompt_text,
                "summary": summary,
                "message": "Prompt is ready to apply. User can click 'Apply' to use this prompt.",
            })

        elif tool_name == "get_signal_pools":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            exchange = args.get("exchange", "all")
            return execute_get_signal_pools(db, exchange)

        elif tool_name == "run_signal_backtest":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            pool_id = args.get("pool_id")
            if pool_id is None:
                return json.dumps({"error": "pool_id is required"})
            symbol = args.get("symbol", "BTC")
            hours = args.get("hours", 24)
            return execute_run_signal_backtest(db, pool_id, symbol, hours)

        # New prompt context tools
        elif tool_name == "get_prompt_context":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            # Use passed prompt_id if args doesn't specify one
            pid = args.get("prompt_id") or prompt_id
            return execute_get_prompt_context(db, pid)

        elif tool_name == "get_trader_details":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            trader_id = args.get("trader_id")
            if trader_id is None:
                return json.dumps({"error": "trader_id is required"})
            return execute_get_trader_details(db, trader_id)

        elif tool_name == "get_decision_list":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            trader_id = args.get("trader_id")
            if trader_id is None:
                return json.dumps({"error": "trader_id is required"})
            limit = args.get("limit", 10)
            return execute_get_decision_list(db, trader_id, limit)

        elif tool_name == "get_decision_details":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            decision_ids = args.get("decision_ids")
            if not decision_ids:
                return json.dumps({"error": "decision_ids is required"})
            fields = args.get("fields")
            return execute_get_decision_details(db, decision_ids, fields)

        elif tool_name == "query_market_data":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            symbol = args.get("symbol")
            if not symbol:
                return json.dumps({"error": "symbol is required"})
            period = args.get("period", "1h")
            exchange = args.get("exchange", "hyperliquid")
            return execute_query_market_data(db, symbol, period, exchange)

        elif tool_name == "query_factors":
            if db is None:
                return json.dumps({"error": "Database session not available"})
            from services.hyper_ai_tools import execute_query_factors

            exchange = args.get("exchange", "hyperliquid")
            symbol = args.get("symbol")
            factor_name = args.get("factor_name")
            forward_period = args.get("forward_period", "4h")
            return execute_query_factors(db, exchange, symbol, factor_name, forward_period)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.error(f"[AI Prompt Gen {request_id}] Tool execution error: {e}")
        return json.dumps({"error": str(e)})
