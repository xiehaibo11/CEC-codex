"""Function Calling tool schemas for AI Attribution Analysis.

ATTRIBUTION_TOOLS is populated at import time by _define_tools().
"""

# Tools schema for Function Calling
ATTRIBUTION_TOOLS = []  # Will be defined below


def _define_tools():
    """Define Function Calling tools for attribution analysis"""
    global ATTRIBUTION_TOOLS
    ATTRIBUTION_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "list_ai_accounts",
                "description": "List all AI trading accounts with their IDs, names, and models. Use this FIRST when user mentions an account by name (e.g., 'Deepseek', 'Claude') to find the account ID.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_attribution_summary",
                "description": "Get trading performance summary including win rate, PnL, trade counts by operation/symbol.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "integer", "description": "Account ID to analyze. Use 0 for all accounts."},
                        "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange to analyze trades from. REQUIRED."},
                        "environment": {"type": "string", "enum": ["testnet", "mainnet"], "description": "Trading environment. REQUIRED for both exchanges."},
                        "days": {"type": "integer", "description": "Number of days to analyze (7, 30, 90)", "default": 30}
                    },
                    "required": ["account_id", "exchange"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_account_strategy",
                "description": "Get account's trading strategy configuration including signal pool and prompt binding.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "integer", "description": "Account ID to query"}
                    },
                    "required": ["account_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_prompt_template",
                "description": "Get the prompt template content used by an account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "integer", "description": "Account ID to get prompt for"}
                    },
                    "required": ["account_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_signal_pool_config",
                "description": "Get signal pool configuration including signals and trigger conditions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pool_id": {"type": "integer", "description": "Signal pool ID to query"}
                    },
                    "required": ["pool_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_trade_decision_chain",
                "description": "Get detailed decision chain for specific trades including AI reasoning and execution results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "integer", "description": "Account ID"},
                        "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange to query trades from. REQUIRED."},
                        "environment": {"type": "string", "enum": ["testnet", "mainnet"], "description": "Trading environment. REQUIRED for both exchanges."},
                        "limit": {"type": "integer", "description": "Number of recent trades to fetch", "default": 10},
                        "filter_type": {"type": "string", "enum": ["all", "wins", "losses"], "description": "Filter by trade outcome"}
                    },
                    "required": ["account_id", "exchange"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "suggest_prompt_modification",
                "description": "Generate a structured prompt modification suggestion card based on diagnosis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short title for the suggestion"},
                        "current_behavior": {"type": "string", "description": "Current prompt behavior causing issues"},
                        "suggested_change": {"type": "string", "description": "Specific prompt modification to apply"},
                        "reason": {"type": "string", "description": "Why this change will improve performance"}
                    },
                    "required": ["title", "current_behavior", "suggested_change", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_factor_attribution",
                "description": "Analyze trading performance grouped by factor signal triggers. Shows which factors led to profitable vs losing trades.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "integer", "description": "Account ID (0 for all)"},
                        "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange. REQUIRED."},
                        "environment": {"type": "string", "enum": ["testnet", "mainnet"], "description": "Environment. REQUIRED."},
                        "days": {"type": "integer", "description": "Analysis period in days", "default": 30}
                    },
                    "required": ["account_id", "exchange"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_factors",
                "description": "Query factor library and effectiveness data. Returns factor values, IC, ICIR, win rate, decay, and IC trend (ic_7d/ic_trend). ic_trend > 1 = factor strengthening recently, < 1 = weakening.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (required)"},
                        "symbol": {"type": "string", "description": "Symbol for effectiveness ranking"},
                        "forward_period": {"type": "string", "enum": ["1h", "4h", "12h", "24h"], "description": "Forward period (default: 4h)"}
                    },
                    "required": ["exchange"]
                }
            }
        }
    ]


# Initialize tools
_define_tools()
