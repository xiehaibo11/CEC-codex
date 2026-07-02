"""Prompt, docs, and tool schema for AI program generation."""
from pathlib import Path

from services.ai_decision_service import convert_tools_to_anthropic
from services.ai_shared_tools import SHARED_SIGNAL_TOOLS

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

def _load_config_text(filename: str) -> str:
    return (_CONFIG_DIR / filename).read_text(encoding="utf-8")

PROGRAM_SYSTEM_PROMPT = (
    _load_config_text("program_generation_system_prompt_intro.md")
    + _load_config_text("program_generation_system_prompt_reference.md")
)
MARKET_API_DOCS = _load_config_text("program_generation_market_api_docs.md")
DECISION_API_DOCS = _load_config_text("program_generation_decision_api_docs.md")

PROGRAM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_market_data",
            "description": "Query current market data for a symbol from specified exchange. MUST call this FIRST before writing any threshold comparisons to understand actual indicator value ranges.",
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
                        "description": "Exchange to query market data from (default: hyperliquid)"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_api_docs",
            "description": "Get detailed documentation for MarketData properties/methods and Decision object.",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_type": {
                        "type": "string",
                        "enum": ["market", "decision", "all"],
                        "description": "Which API documentation to retrieve (market=MarketData, decision=Decision/ActionType)"
                    }
                },
                "required": ["api_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_code",
            "description": "Get the current code of the program being edited. Returns empty if creating new program.",
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
            "name": "validate_code",
            "description": "Validate Python code syntax and check for common errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to validate"
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_run_code",
            "description": "Test run code with real market data. Returns execution result or detailed error.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to test"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol for market data context (e.g., BTC, ETH)"
                    }
                },
                "required": ["code", "symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "quick_verify_strategy",
            "description": "Quick verify strategy code on historical data. Simulates real execution with signal pool triggers and/or scheduled triggers. Returns full backtest metrics including PnL, win rate, max drawdown, profit factor. Run this BEFORE suggesting to save code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Strategy code to verify"
                    },
                    "exchange": {
                        "type": "string",
                        "enum": ["hyperliquid", "binance"],
                        "description": "Exchange to use for historical data"
                    },
                    "signal_pool_id": {
                        "type": "integer",
                        "description": "Signal pool ID for signal-based triggers (optional, can combine with scheduled)"
                    },
                    "scheduled_interval_minutes": {
                        "type": "integer",
                        "description": "Scheduled trigger interval in minutes (optional, can combine with signal pool)"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol (default: BTC)"
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Backtest duration in hours (default: 168 = 7 days)"
                    }
                },
                "required": ["code", "exchange"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_save_code",
            "description": "Propose code to save. Does NOT save directly - returns suggestion for user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Final Python code to suggest saving"
                    },
                    "name": {
                        "type": "string",
                        "description": "Suggested program name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what the program does"
                    }
                },
                "required": ["code", "name", "description"]
            }
        }
    }
]

# Backtest analysis tools - for analyzing strategy backtest results
BACKTEST_ANALYSIS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_backtest_history",
            "description": "Get backtest history for the current program. Use this when user asks to analyze backtest results or strategy performance. Returns list of backtests with key metrics (PnL, win rate, drawdown).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of backtests to return (default: 10)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trigger_list",
            "description": "Get trigger summary list for a specific backtest. Returns overview of each trigger: index, time, symbol, action, equity change, PnL. Use this to identify problematic triggers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "backtest_id": {
                        "type": "integer",
                        "description": "Backtest ID from get_backtest_history"
                    }
                },
                "required": ["backtest_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trigger_details",
            "description": "Get detailed info for specific triggers. Use this to analyze why certain decisions were made. Supports batch query and field filtering to save tokens.",
            "parameters": {
                "type": "object",
                "properties": {
                    "backtest_id": {
                        "type": "integer",
                        "description": "Backtest ID"
                    },
                    "indexes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Trigger indexes to query (e.g., [5, 8, 12])"
                    },
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["summary", "input", "output", "queries", "logs"]
                        },
                        "description": "Fields to include. Default all. summary=basic info, input=decision_input, output=decision_output, queries=data_queries, logs=execution_logs"
                    }
                },
                "required": ["backtest_id", "indexes"]
            }
        }
    }
]

# Factor query tool (reused from hyper_ai_tools)
FACTOR_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "query_factors",
        "description": "Query factor library and effectiveness data. Without symbol: returns factor list with names (for use in data.get_factor(symbol, factor_name, period)). With symbol: returns factor values and effectiveness ranking. Response includes IC, ICIR, win_rate, decay_half_life_hours.",
        "parameters": {
            "type": "object",
            "properties": {
                "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (required)"},
                "symbol": {"type": "string", "description": "Trading symbol (e.g., BTC). If omitted, returns factor library list."},
                "factor_name": {"type": "string", "description": "Specific factor name for detailed info"},
                "forward_period": {"type": "string", "enum": ["1h", "4h", "12h", "24h"], "description": "Forward period for effectiveness (default: 4h)"}
            },
            "required": ["exchange"]
        }
    }
}

# Combine all tools
PROGRAM_TOOLS = PROGRAM_TOOLS + BACKTEST_ANALYSIS_TOOLS + SHARED_SIGNAL_TOOLS + [FACTOR_QUERY_TOOL]

PROGRAM_TOOLS_ANTHROPIC = convert_tools_to_anthropic(PROGRAM_TOOLS)
