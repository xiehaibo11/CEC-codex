"""OpenAI tool definitions for Hyper AI sub-agents."""


# Sub-agents inherit Hyper AI's LLM configuration, no account_id needed.
SUBAGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "call_prompt_ai",
            "description": """Call Prompt AI to generate or optimize trading prompts.
Use this when user wants to:
- Create a new trading prompt from scratch
- Optimize an existing prompt
- Add/modify variables in a prompt
- Validate prompt syntax

The sub-agent has access to variables reference and can preview prompts with real data.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description for Prompt AI",
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Continue a previous Prompt AI conversation",
                    },
                    "prompt_id": {
                        "type": "integer",
                        "description": "Optional: Prompt ID if editing existing prompt",
                    },
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_program_ai",
            "description": """Call Program AI to write or modify trading strategy code.
Use this when user wants to:
- Create a new trading program/strategy
- Modify existing program code
- Debug or fix code issues
- Add new features to a program

The sub-agent can query market data, validate code, and run test executions.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description for Program AI",
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Continue a previous Program AI conversation",
                    },
                    "program_id": {
                        "type": "integer",
                        "description": "Optional: Program ID if editing existing program",
                    },
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_signal_ai",
            "description": """Call Signal AI to configure signal pools.
Use this when user wants to:
- Create a new signal pool
- Modify signal pool configuration
- Add/remove signals from a pool
- Run signal backtest

The sub-agent can query available signals and run backtests.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description for Signal AI",
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Continue a previous Signal AI conversation",
                    },
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_attribution_ai",
            "description": """Call Attribution AI to analyze trading performance.
Use this when user wants to:
- Analyze why a trade succeeded or failed
- Get performance attribution report
- Understand decision patterns
- Review historical trades

The sub-agent can query decision logs and provide detailed analysis.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description for Attribution AI",
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Continue a previous Attribution AI conversation",
                    },
                },
                "required": ["task"],
            },
        },
    },
]
