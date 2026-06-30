"""Hyper AI tool schema catalog: binding, update, delete, factor, external, and skill tools."""

MANAGEMENT_TOOL_SCHEMAS = [
    # --- Binding Tools: assemble components ---
    {
        "type": "function",
        "function": {
            "name": "bind_prompt_to_trader",
            "description": "Bind a prompt template to an AI Trader (one-to-one, replaces existing binding).",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "AI Trader ID"},
                    "prompt_id": {"type": "integer", "description": "Prompt template ID to bind"}
                },
                "required": ["trader_id", "prompt_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bind_program_to_trader",
            "description": "Create a program binding for an AI Trader with trigger config (many-to-many). IMPORTANT: exchange must match signal_pool exchange.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "AI Trader ID"},
                    "program_id": {"type": "integer", "description": "Trading program ID"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange to trade on (REQUIRED). Must match signal_pool exchange."},
                    "signal_pool_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Signal pool IDs for triggering. Their exchange must match the binding exchange."
                    },
                    "trigger_interval": {"type": "integer", "description": "Scheduled trigger interval in seconds (default: 300)"},
                    "is_active": {"type": "boolean", "description": "Whether binding is active (default: true)"}
                },
                "required": ["trader_id", "program_id", "exchange"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_trader_strategy",
            "description": "Update trigger configuration for a Prompt-based AI Trader (signal pools, scheduled trigger, interval, exchange).",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "AI Trader ID"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Target exchange. MUST match the trader's wallet exchange."},
                    "signal_pool_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Signal pool IDs to bind"
                    },
                    "scheduled_trigger_enabled": {"type": "boolean", "description": "Enable scheduled trigger"},
                    "trigger_interval": {"type": "integer", "description": "Trigger interval in seconds"}
                },
                "required": ["trader_id"]
            }
        }
    },
    # --- Update Tools ---
    {
        "type": "function",
        "function": {
            "name": "update_ai_trader",
            "description": "Update AI Trader settings (name, LLM config). Tests LLM connection if model/base_url/api_key changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "AI Trader ID"},
                    "name": {"type": "string", "description": "New display name"},
                    "model": {"type": "string", "description": "New LLM model name"},
                    "base_url": {"type": "string", "description": "New LLM API base URL"},
                    "api_key": {"type": "string", "description": "New LLM API key"}
                },
                "required": ["trader_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_program_binding",
            "description": "Update a program binding's configuration (signal pools, trigger interval, activation, params).",
            "parameters": {
                "type": "object",
                "properties": {
                    "binding_id": {"type": "integer", "description": "Program binding ID"},
                    "signal_pool_ids": {"type": "array", "items": {"type": "integer"}, "description": "New signal pool IDs"},
                    "trigger_interval": {"type": "integer", "description": "New trigger interval in seconds"},
                    "scheduled_trigger_enabled": {"type": "boolean", "description": "Enable/disable scheduled trigger"},
                    "is_active": {"type": "boolean", "description": "Activate or deactivate the binding"},
                    "params_override": {"type": "object", "description": "Parameter overrides for the program"}
                },
                "required": ["binding_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_signal_pool",
            "description": "Update signal pool settings (name, enabled, logic, signal_ids). Signal IDs must belong to the same exchange as the pool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_id": {"type": "integer", "description": "Signal pool ID"},
                    "pool_name": {"type": "string", "description": "New display name"},
                    "enabled": {"type": "boolean", "description": "Enable or disable the pool"},
                    "logic": {"type": "string", "enum": ["AND", "OR"], "description": "Logic operator"},
                    "signal_ids": {"type": "array", "items": {"type": "integer"}, "description": "Replace signal definitions in this pool. All signals must match the pool's exchange."}
                },
                "required": ["pool_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_prompt_binding",
            "description": "Update which prompt template is bound to an AI Trader. Replaces the current binding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "AI Trader ID"},
                    "prompt_id": {"type": "integer", "description": "New prompt template ID to bind"}
                },
                "required": ["trader_id", "prompt_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save or update long-term memory with intelligent deduplication. The system automatically compares against existing memories and decides to ADD, UPDATE (merge/replace), or SKIP. To update an existing memory, just call this with the corrected content — the old version will be replaced automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["preference", "decision", "lesson", "insight", "context"],
                        "description": "Memory category: preference (trading style/risk), decision (config changes), lesson (from wins/losses), insight (market patterns), context (general)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Concise, self-contained memory content. Should be understandable without conversation context."
                    },
                    "importance": {
                        "type": "number",
                        "description": "Importance score 0.0-1.0. Default 0.5. Use 0.7+ for key lessons/preferences, 0.3 for minor context."
                    }
                },
                "required": ["category", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_trader",
            "description": "Soft-delete an AI Trader. Checks for bindings and open positions first. Returns dependency list if blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "AI Trader ID to delete"}
                },
                "required": ["trader_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_prompt_template",
            "description": "Soft-delete a Prompt Template. Checks for active bindings first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "integer", "description": "Prompt Template ID to delete"}
                },
                "required": ["prompt_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_signal_definition",
            "description": "Soft-delete a Signal Definition. Checks for signal pool references first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_id": {"type": "integer", "description": "Signal Definition ID to delete"}
                },
                "required": ["signal_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_signal_pool",
            "description": "Soft-delete a Signal Pool. Checks for strategy and program binding references first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_id": {"type": "integer", "description": "Signal Pool ID to delete"}
                },
                "required": ["pool_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_trading_program",
            "description": "Soft-delete a Trading Program. Checks for active bindings first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "program_id": {"type": "integer", "description": "Trading Program ID to delete"}
                },
                "required": ["program_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_prompt_binding",
            "description": "Soft-delete a Prompt Binding (unbind prompt from trader).",
            "parameters": {
                "type": "object",
                "properties": {
                    "binding_id": {"type": "integer", "description": "Prompt Binding ID to delete"}
                },
                "required": ["binding_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_program_binding",
            "description": "Soft-delete a Program Binding. Must be deactivated (is_active=false) first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "binding_id": {"type": "integer", "description": "Program Binding ID to delete"}
                },
                "required": ["binding_id"]
            }
        }
    },
    # --- Factor System Tools ---
    {
        "type": "function",
        "function": {
            "name": "query_factors",
            "description": "Query factor library and effectiveness data. Without symbol: returns factor list. With symbol: returns factor values and effectiveness ranking. Fields: decay_half_life_hours (spatial dimension): positive=half-life in hours (IC decays across forward periods), -1=persistent (IC holds across periods). ic_7d: average IC over recent 7 days. ic_trend (temporal dimension): ic_7d / ic_30d ratio, >1 = factor strengthening recently, <1 = weakening, helps detect if factor is losing effectiveness over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (required)"},
                    "symbol": {"type": "string", "description": "Trading symbol (e.g., BTC). If omitted, returns factor library list."},
                    "factor_name": {"type": "string", "description": "Specific factor name for detailed info + history"},
                    "forward_period": {"type": "string", "enum": ["1h", "4h", "12h", "24h"], "description": "Forward period for effectiveness (default: 4h)"},
                    "days": {"type": "integer", "description": "Number of days of history to return when querying a specific factor (default: 30, max: 365). Use larger values for long-term trend analysis."}
                },
                "required": ["exchange"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_factor",
            "description": "Evaluate a custom factor expression against real market data. Returns syntax validation, latest value, and IC/ICIR/win_rate for each forward period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Factor expression (e.g., 'EMA(close, 7) / EMA(close, 21) - 1')"},
                    "symbol": {"type": "string", "description": "Trading symbol (e.g., BTC)"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (required)"}
                },
                "required": ["expression", "symbol", "exchange"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_factor",
            "description": "Save a custom factor expression to the factor library.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Factor name (unique, descriptive)"},
                    "expression": {"type": "string", "description": "Factor expression"},
                    "description": {"type": "string", "description": "Brief description of what the factor measures"}
                },
                "required": ["name", "expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_factor",
            "description": "Edit an existing custom factor. Only custom factors can be edited, not built-in ones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "factor_id": {"type": "integer", "description": "Custom factor ID (required)"},
                    "name": {"type": "string", "description": "New name (optional)"},
                    "expression": {"type": "string", "description": "New expression (optional)"},
                    "description": {"type": "string", "description": "New description (optional)"}
                },
                "required": ["factor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compute_factor",
            "description": "Run computation for a specific factor across all watchlist symbols on an exchange. Updates factor values and effectiveness metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "factor_name": {"type": "string", "description": "Factor name to compute"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (required)"}
                },
                "required": ["factor_name", "exchange"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_factor_functions",
            "description": "Get the full list of supported factor expression functions, grouped by category. Call this BEFORE designing or modifying factor expressions, so you know exactly which functions are available and their signatures.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional). Leave empty for all categories."
                    }
                },
                "required": []
            }
        }
    }
]

# --- External Tools (require user-provided API keys) ---
EXTERNAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for quant research, market news, factor ideas, or any external information. Use when user asks about recent events, research papers, trading strategies from the internet, or when you need external knowledge to design factors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (English recommended for better results)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max number of results (default 5, max 10)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch the full content of a web page and convert it to clean Markdown text. Use AFTER web_search to retrieve detailed content from a specific URL found in search results. Supports HTML pages, blog posts, documentation, and GitHub files. For academic papers, fetch the abstract page rather than the PDF directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch content from"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum content length in characters (default 8000, max 15000)",
                        "default": 8000
                    }
                },
                "required": ["url"]
            }
        }
    }
]

# --- Skill System Tools ---
# These tools load workflow guidance into the AI's context (Level 2 & 3 loading).
# They do NOT perform any actions — they provide step-by-step instructions
# for the AI to follow when executing complex multi-step tasks.
# See backend/skills/*/SKILL.md for skill definitions.
SKILL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "Load a skill workflow guide into your context. This does NOT perform any action — it provides you with step-by-step instructions for a specific task type. Use this when a user's request matches one of your available skills.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to load (e.g., 'prompt-strategy-setup', 'trader-diagnosis')"
                    }
                },
                "required": ["skill_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "load_skill_reference",
            "description": "Load a reference document from a skill's references/ directory. Use this when a loaded skill mentions additional reference materials you should consult.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill"
                    },
                    "reference_file": {
                        "type": "string",
                        "description": "Filename of the reference document (e.g., 'signal-design-guide.md')"
                    }
                },
                "required": ["skill_name", "reference_file"]
            }
        }
    }
]
