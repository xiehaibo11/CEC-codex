"""Hyper AI tool schema catalog: read, market, write/create, list, and event-contract tools."""

OPERATION_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_overview",
            "description": "Get high-level system status: wallets, AI traders, strategies, signal pools, positions.",
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
            "name": "get_wallet_status",
            "description": "Get wallet balance and position summary (read-only, no credentials exposed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "exchange": {
                        "type": "string",
                        "enum": ["hyperliquid", "binance", "all"],
                        "description": "Filter by exchange (default: all)"
                    },
                    "environment": {
                        "type": "string",
                        "enum": ["testnet", "mainnet", "all"],
                        "description": "Filter by environment (default: all)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_api_reference",
            "description": "Get API reference docs for Prompt variables or Program MarketData/Decision APIs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {
                        "type": "string",
                        "enum": ["prompt", "program"],
                        "description": "Document type: prompt (variables) or program (MarketData/Decision API)"
                    },
                    "api_type": {
                        "type": "string",
                        "enum": ["market", "decision", "all"],
                        "description": "For program only: which API docs (default: all)"
                    },
                    "lang": {
                        "type": "string",
                        "enum": ["en", "zh"],
                        "description": "Language (default: en)"
                    }
                },
                "required": ["doc_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_klines",
            "description": "Get K-line/candlestick data for a symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol (e.g., BTC, ETH)"},
                    "period": {"type": "string", "enum": ["1m", "5m", "15m", "1h", "4h", "1d"], "description": "K-line period (default: 1h)"},
                    "limit": {"type": "integer", "description": "Number of candles (default: 50, max: 200)"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (default: hyperliquid)"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_regime",
            "description": "Get current market regime classification for a symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
                    "period": {"type": "string", "enum": ["1m", "5m", "15m", "1h", "4h", "1d"], "description": "Time period (default: 1h)"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (default: hyperliquid)"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_flow",
            "description": "Get market flow data (CVD, OI, Funding, etc.) for a symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
                    "period": {"type": "string", "enum": ["1m", "5m", "15m", "1h", "4h", "1d"], "description": "Time period (default: 1h)"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (default: hyperliquid)"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_logs",
            "description": "Get recent system logs enriched with error registry (severity, exchange relevance, suggestions). Logs marked 'other_exchange' are from an exchange the user doesn't use — deprioritize them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["error", "warning", "all"], "description": "Log level filter (default: error)"},
                    "limit": {"type": "integer", "description": "Max entries (default: 20, max: 50)"},
                    "trader_id": {"type": "integer", "description": "Filter by AI Trader ID"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_contact_config",
            "description": "Get support channel URLs (Twitter, Telegram, GitHub).",
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
            "name": "get_trading_environment",
            "description": "Get current global trading environment (testnet/mainnet). This affects which wallets and data sources are used system-wide.",
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
            "name": "get_watchlist",
            "description": "Get symbol watchlist configuration for all exchanges. Shows which symbols are being monitored for data collection and trading. Also indicates if user is still using default symbols.",
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
            "name": "update_watchlist",
            "description": "Update symbol watchlist for a specific exchange. IMPORTANT: Always call get_watchlist first to show current config and get user confirmation before updating.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exchange": {
                        "type": "string",
                        "enum": ["hyperliquid", "binance"],
                        "description": "Exchange to update watchlist for"
                    },
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of symbols to monitor (e.g., ['BTC', 'ETH', 'SOL']). Max 10 symbols."
                    }
                },
                "required": ["exchange", "symbols"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_trader_issues",
            "description": "Check why an AI Trader is not triggering and provide actionable suggestions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "AI Trader ID to diagnose"}
                },
                "required": ["trader_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_tracked_address",
            "description": "Get CoinGlass Hyperliquid wallet position detail for a tracked wallet address. Returns factual position, margin, and PnL data available from CoinGlass.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Tracked wallet address to analyze"
                    }
                },
                "required": ["address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_tracked_wallets",
            "description": "Get the current CoinGlass wallet tracking status and wallet addresses currently available to CEC-codex wallet-tracking signal pools.",
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
            "name": "get_strategy_radar_universe",
            "description": "Get Strategy Radar's currently supported symbol/period/exchange/regime combinations. Call before searching Strategy Radar so unsupported symbols are not inferred.",
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
            "name": "search_strategy_radar",
            "description": "Search current Strategy Radar candidates for a supported symbol and period. Results are quality-filtered strategy ideas, not profitability rankings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Supported trading symbol from get_strategy_radar_universe, e.g. BTC"},
                    "period": {"type": "string", "enum": ["1h", "4h", "1d"], "description": "Radar period (default: 1h)"},
                    "regime": {"type": "string", "description": "Optional requested regime. Omit to use current Radar regime for the symbol/period."},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Optional exchange filter"},
                    "strategy_type": {"type": "string", "description": "Optional strategy type filter"},
                    "sort_by": {"type": "string", "enum": ["relevance", "quality", "newest"], "description": "Optional sort mode. Default is relevance."},
                    "risk_level": {"type": "string", "enum": ["Low", "Medium", "High"], "description": "Optional risk filter."},
                    "timeframe": {"type": "string", "enum": ["1h", "4h", "1d", "multi"], "description": "Optional card timeframe filter."},
                    "limit": {"type": "integer", "description": "Max results (default: 5, max: 10)"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_signal_pool",
            "description": "Create a signal pool from complete signal configuration. Automatically creates signal definitions and combines them into a pool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_name": {"type": "string", "description": "Display name for the pool"},
                    "symbol": {"type": "string", "description": "Symbol to monitor (e.g., BTC, ETH)"},
                    "signals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "metric": {"type": "string", "description": "Metric name. Standard: cvd, oi_delta_percent, order_imbalance, taker_volume, price_change, volatility. Factor: factor:<name> (e.g., factor:RSI21, factor:ADX14)."},
                                "operator": {"type": "string", "description": "Comparison operator (greater_than, less_than, etc.). NOT used for taker_volume."},
                                "threshold": {"type": "number", "description": "Threshold value. NOT used for taker_volume."},
                                "time_window": {"type": "string", "description": "Time window (e.g., 5m, 15m, 1h)"},
                                "direction": {"type": "string", "enum": ["buy", "sell", "any"], "description": "taker_volume ONLY: dominant side"},
                                "ratio_threshold": {"type": "number", "description": "taker_volume ONLY: buy/sell ratio multiplier (e.g., 1.5 = 50% more)"},
                                "volume_threshold": {"type": "number", "description": "taker_volume ONLY: minimum total volume in USD"}
                            }
                        },
                        "description": "Array of signal conditions. Standard signals use metric/operator/threshold/time_window. taker_volume uses metric/direction/ratio_threshold/volume_threshold/time_window instead."
                    },
                    "logic": {"type": "string", "enum": ["AND", "OR"], "description": "Logic operator (default: AND)"},
                    "exchange": {"type": "string", "enum": ["hyperliquid", "binance"], "description": "Exchange (default: hyperliquid)"},
                    "description": {"type": "string", "description": "Optional description for the pool"}
                },
                "required": ["pool_name", "symbol", "signals"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_prompt",
            "description": "Create or update a trading prompt template.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "integer", "description": "Prompt ID to update (omit for create)"},
                    "name": {"type": "string", "description": "Display name"},
                    "description": {"type": "string", "description": "Brief description"},
                    "template_text": {"type": "string", "description": "Main prompt content"}
                },
                "required": ["name", "template_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_program",
            "description": "Create or update a trading program.",
            "parameters": {
                "type": "object",
                "properties": {
                    "program_id": {"type": "integer", "description": "Program ID to update (omit for create)"},
                    "name": {"type": "string", "description": "Display name"},
                    "description": {"type": "string", "description": "Brief description"},
                    "code": {"type": "string", "description": "Python strategy code"}
                },
                "required": ["name", "code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_ai_trader",
            "description": "Create a new AI Trader with LLM config. Tests LLM connection before saving. Strategy binding and wallet setup are done separately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Display name for the trader"},
                    "model": {"type": "string", "description": "LLM model name (e.g., gpt-4o, deepseek-v4-flash, claude-3.5-sonnet)"},
                    "base_url": {"type": "string", "description": "LLM API base URL (e.g., https://api.openai.com/v1)"},
                    "api_key": {"type": "string", "description": "LLM API key"}
                },
                "required": ["name", "model", "base_url", "api_key"]
            }
        }
    },
    # --- Query Tools: list resources ---
    {
        "type": "function",
        "function": {
            "name": "list_traders",
            "description": "List all AI Traders with bindings, strategies, wallet and trading status. Pass trader_id to get one trader's full detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "Optional: specific AI Trader ID for detail view"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_signal_pools",
            "description": "List all signal pools with IDs, symbols, exchange, and trigger conditions. Pass pool_id to get one pool's full detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_id": {"type": "integer", "description": "Optional: specific signal pool ID for detail view"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_strategies",
            "description": "List all trading prompts and programs with IDs, names, and binding status. Pass strategy_id + strategy_type to get full content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {"type": "integer", "description": "Optional: specific strategy ID for detail view"},
                    "strategy_type": {"type": "string", "enum": ["prompt", "program"], "description": "Required when strategy_id is provided"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_prompt_backtests",
            "description": "List Prompt Backtest tasks or inspect one task's result summary. Read-only. Use this when the user asks about AI Trader prompt backtest history, progress, or decision changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trader_id": {"type": "integer", "description": "Optional AI Trader ID to filter task history"},
                    "task_id": {"type": "integer", "description": "Optional Prompt Backtest task ID to inspect in detail"},
                    "limit": {"type": "integer", "description": "Max tasks to return when listing history (default 10, max 20)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "predict_event_contract_5m",
            "description": "Run the 5-minute event contract prediction engine for a symbol. Default mode calls the configured LLM for 30-role AI confirmation; rule_only uses deterministic prefilter rules only. Read-only; does not place trades.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol, e.g. BTC"},
                    "exchange": {"type": "string", "enum": ["binance", "hyperliquid"], "description": "Exchange (default: binance)"},
                    "period": {"type": "string", "enum": ["1m", "3m", "5m", "15m", "30m", "1h"], "description": "Main K-line period (default: 1m)"},
                    "consensus_threshold": {"type": "integer", "description": "Consensus threshold: 30, 29, or 28 (default: 30)"},
                    "consensus_mode": {"type": "string", "enum": ["ai_confirmed", "rule_only"], "description": "ai_confirmed calls the configured LLM; rule_only uses deterministic rules only"},
                    "ai_trader_id": {"type": "integer", "description": "Optional AI Trader account ID for LLM confirmation"},
                    "enable_l2_features": {"type": "boolean", "description": "Use locally collected L2 orderbook snapshots for depth, imbalance, and spread factors (default: true)"},
                    "min_l2_coverage_pct": {"type": "number", "description": "Minimum local L2 coverage percentage when enabled (default: 96)"},
                    "strict_l2_quality": {"type": "boolean", "description": "Fail the prediction if enabled L2 data is below the minimum coverage"},
                    "enable_coinglass_features": {"type": "boolean", "description": "Use CoinGlass historical CVD, taker flow, OI, funding, and liquidation factors when a server key is configured"},
                    "min_coinglass_coverage_pct": {"type": "number", "description": "Minimum CoinGlass coverage percentage when enabled (default: 96)"},
                    "strict_coinglass_quality": {"type": "boolean", "description": "Fail the prediction if enabled CoinGlass data is below the minimum coverage"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_event_contract_backtest",
            "description": "Run a 5-minute event contract historical backtest using K-lines, rule prefiltering, optional real LLM 30-role AI confirmation, and expiry settlement. Saves the run and returns summary plus sample trades.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol, e.g. BTC"},
                    "exchange": {"type": "string", "enum": ["binance", "hyperliquid"], "description": "Exchange (default: binance)"},
                    "period": {"type": "string", "enum": ["1m", "3m", "5m", "15m", "30m", "1h"], "description": "Main K-line period (default: 1m)"},
                    "start_time": {"type": "string", "description": "ISO start time, e.g. 2026-06-20T00:00:00Z"},
                    "end_time": {"type": "string", "description": "ISO end time"},
                    "consensus_threshold": {"type": "integer", "description": "Consensus threshold: 30, 29, or 28 (default: 30)"},
                    "initial_balance": {"type": "number", "description": "Initial balance (default: 10000)"},
                    "stake_amount": {"type": "number", "description": "Stake per event contract (default: 100)"},
                    "consensus_mode": {"type": "string", "enum": ["ai_confirmed", "rule_only"], "description": "ai_confirmed calls the configured LLM for candidate signals; rule_only uses deterministic rules only"},
                    "ai_trader_id": {"type": "integer", "description": "Optional AI Trader account ID for LLM confirmation"},
                    "max_ai_evaluations": {"type": "integer", "description": "Maximum LLM-confirmed candidate signals in this backtest (default: 20)"},
                    "enable_l2_features": {"type": "boolean", "description": "Use locally collected L2 orderbook snapshots for depth, imbalance, and spread factors (default: true)"},
                    "min_l2_coverage_pct": {"type": "number", "description": "Minimum local L2 coverage percentage when enabled (default: 96)"},
                    "strict_l2_quality": {"type": "boolean", "description": "Fail the backtest if enabled L2 data is below the minimum coverage"},
                    "enable_coinglass_features": {"type": "boolean", "description": "Use CoinGlass historical CVD, taker flow, OI, funding, and liquidation factors when a server key is configured"},
                    "min_coinglass_coverage_pct": {"type": "number", "description": "Minimum CoinGlass coverage percentage when enabled (default: 96)"},
                    "strict_coinglass_quality": {"type": "boolean", "description": "Fail the backtest if enabled CoinGlass data is below the minimum coverage"}
                },
                "required": ["symbol", "start_time", "end_time"]
            }
        }
    },
]
