"""
AI Prompt Shared Tools - Tool definitions (OpenAI format)

Tool schemas exposed to the Prompt AI for prompt-context access, trader
details, decision history, and market data queries.
"""

# Tool definitions in OpenAI format
PROMPT_CONTEXT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_prompt_context",
            "description": "Get current prompt content and list of AI Traders using this prompt. Call this first to understand what you're editing.",
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
            "name": "get_trader_details",
            "description": "Get AI Trader configuration including exchange, environment, leverage, selected symbols, and bound signal pool details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {
                        "type": "integer",
                        "description": "AI Trader ID (account_id) to get details for"
                    }
                },
                "required": ["trader_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_decision_list",
            "description": "Get recent AI decision history (summary only). Returns decision IDs, time, trigger type, operation, and execution status. Use get_decision_details for full prompt/reasoning content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {
                        "type": "integer",
                        "description": "AI Trader ID to get decisions for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of decisions to return (default: 10, max: 20)",
                        "default": 10
                    }
                },
                "required": ["trader_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_decision_details",
            "description": "Get detailed info for specific decisions including prompt, reasoning, and decision output. Use fields parameter to control what to retrieve.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of decision IDs to get details for (max 5)"
                    },
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["summary", "prompt", "reasoning", "decision"]
                        },
                        "description": "Fields to include: summary (basic info), prompt (rendered prompt), reasoning (AI thinking), decision (output JSON). Default: ['summary']"
                    }
                },
                "required": ["decision_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_market_data",
            "description": "Query current market data and technical indicators for a symbol. Use this to understand actual indicator value ranges before writing thresholds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol (e.g., BTC, ETH)"
                    },
                    "period": {
                        "type": "string",
                        "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                        "description": "Time period for indicators (default: 1h)"
                    },
                    "exchange": {
                        "type": "string",
                        "enum": ["hyperliquid", "binance"],
                        "description": "Exchange to query data from (default: hyperliquid)"
                    }
                },
                "required": ["symbol"]
            }
        }
    }
]
