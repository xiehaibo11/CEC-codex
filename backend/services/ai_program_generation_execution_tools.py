"""Tool dispatcher and sandbox checks for AI program generation."""
import json
import logging
import traceback
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import TradingProgram
from services.ai_program_generation_backtest_tools import (
    _get_backtest_history,
    _get_trigger_details,
    _get_trigger_list,
    _quick_verify_strategy,
)
from services.ai_program_generation_config import DECISION_API_DOCS, MARKET_API_DOCS
from services.ai_program_generation_market_tools import _query_market_data
from services.ai_shared_tools import execute_get_signal_pools, execute_run_signal_backtest

logger = logging.getLogger(__name__)

def _execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    db: Session,
    program_id: Optional[int],
    user_id: int
) -> str:
    """Execute a tool and return result as string."""
    try:
        if tool_name == "query_market_data":
            symbol = arguments.get("symbol", "BTC")
            period = arguments.get("period", "1h")
            exchange = arguments.get("exchange", "hyperliquid")
            return _query_market_data(db, symbol, period, exchange)

        elif tool_name == "get_api_docs":
            api_type = arguments.get("api_type", "all")
            if api_type == "market":
                return MARKET_API_DOCS
            elif api_type == "decision":
                return DECISION_API_DOCS
            else:
                return MARKET_API_DOCS + "\n" + DECISION_API_DOCS

        elif tool_name == "get_current_code":
            if program_id:
                program = db.query(TradingProgram).filter(
                    TradingProgram.id == program_id,
                    TradingProgram.user_id == user_id,
                    TradingProgram.is_deleted != True
                ).first()
                if program:
                    return f"Current program: {program.name}\n\n```python\n{program.code}\n```"
            return "No existing code. This is a new program."

        elif tool_name == "validate_code":
            code = arguments.get("code", "")
            return _validate_python_code(code)

        elif tool_name == "test_run_code":
            code = arguments.get("code", "")
            symbol = arguments.get("symbol", "BTC")
            return _test_run_code(db, code, symbol)

        elif tool_name == "quick_verify_strategy":
            code = arguments.get("code", "")
            exchange = arguments.get("exchange", "hyperliquid")
            signal_pool_id = arguments.get("signal_pool_id")
            scheduled_interval_minutes = arguments.get("scheduled_interval_minutes")
            symbol = arguments.get("symbol", "BTC")
            hours = arguments.get("hours", 168)
            return _quick_verify_strategy(
                db, code, exchange,
                signal_pool_id, scheduled_interval_minutes, symbol, hours
            )

        elif tool_name == "suggest_save_code":
            code = arguments.get("code", "")
            name = arguments.get("name", "Untitled Program")
            description = arguments.get("description", "")
            # Return suggestion format - frontend will show confirmation dialog
            return json.dumps({
                "type": "save_suggestion",
                "code": code,
                "name": name,
                "description": description,
                "message": "Code ready to save. User confirmation required."
            })

        elif tool_name == "get_signal_pools":
            exchange = arguments.get("exchange", "all")
            return execute_get_signal_pools(db, exchange)

        elif tool_name == "run_signal_backtest":
            pool_id = arguments.get("pool_id")
            if pool_id is None:
                return json.dumps({"error": "pool_id is required"})
            symbol = arguments.get("symbol", "BTC")
            hours = arguments.get("hours", 24)
            return execute_run_signal_backtest(db, pool_id, symbol, hours)

        # Backtest analysis tools
        elif tool_name == "get_backtest_history":
            limit = arguments.get("limit", 10)
            return _get_backtest_history(db, program_id, user_id, limit)

        elif tool_name == "get_trigger_list":
            backtest_id = arguments.get("backtest_id")
            if backtest_id is None:
                return json.dumps({"error": "backtest_id is required"})
            return _get_trigger_list(db, backtest_id)

        elif tool_name == "get_trigger_details":
            backtest_id = arguments.get("backtest_id")
            indexes = arguments.get("indexes", [])
            fields = arguments.get("fields")
            if backtest_id is None:
                return json.dumps({"error": "backtest_id is required"})
            return _get_trigger_details(db, backtest_id, indexes, fields)

        elif tool_name == "query_factors":
            from services.hyper_ai_tools import execute_query_factors
            exchange = arguments.get("exchange", "hyperliquid")
            symbol = arguments.get("symbol")
            factor_name = arguments.get("factor_name")
            forward_period = arguments.get("forward_period", "4h")
            return execute_query_factors(db, exchange, symbol, factor_name, forward_period)

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.error(f"Tool execution error: {tool_name} - {e}")
        return f"Error executing {tool_name}: {str(e)}"


def _format_tool_calls_log(tool_calls_log: List[Dict], reasoning_snapshot: str) -> str:
    """Format tool calls log and reasoning as Markdown for storage and display.

    Interleaves reasoning and tool calls by round number for better readability.
    """
    if not tool_calls_log and not reasoning_snapshot:
        return ""

    lines = ["<details>", "<summary>Analysis Process</summary>", ""]

    # Parse reasoning by rounds into a dict
    reasoning_by_round = {}
    if reasoning_snapshot:
        rounds = reasoning_snapshot.split("\n[Round ")
        for round_text in rounds:
            if not round_text.strip():
                continue
            if round_text.startswith("[Round "):
                round_text = round_text[7:]
            parts = round_text.split("]\n", 1)
            if len(parts) == 2:
                try:
                    round_num = int(parts[0])
                    content = parts[1].strip()
                    if len(content) > 500:
                        content = content[:500] + "..."
                    content = content.replace("```", "'''")
                    reasoning_by_round[round_num] = content
                except ValueError:
                    pass

    # Determine max round from both sources
    max_round = 0
    if reasoning_by_round:
        max_round = max(max_round, max(reasoning_by_round.keys()))
    if tool_calls_log:
        max_round = max(max_round, len(tool_calls_log))

    # Interleave by round
    tool_idx = 0
    for round_num in range(1, max_round + 1):
        # Add reasoning for this round if exists
        if round_num in reasoning_by_round:
            lines.append(f"**Round {round_num} - Reasoning:**")
            lines.append(f"> {reasoning_by_round[round_num]}")
            lines.append("")

        # Add tool call for this round if exists
        if tool_idx < len(tool_calls_log):
            entry = tool_calls_log[tool_idx]
            tool_name = entry.get("tool", "unknown")
            args = entry.get("args", {})
            result = entry.get("result", "")

            lines.append(f"**Round {round_num} - Tool: `{tool_name}`**")
            # Include all arguments except code in one line
            args_str = ", ".join(f"{k}={v}" for k, v in args.items() if k != "code")
            if args_str:
                lines.append(f"- Arguments: {args_str}")
            # Include code separately in a code block for full context
            if "code" in args:
                code_content = args["code"]
                lines.append("- Code:")
                lines.append("```python")
                lines.append(code_content)
                lines.append("```")
            result_preview = result[:200] + "..." if len(result) > 200 else result
            result_preview = result_preview.replace("```", "'''").replace("\n", " ")
            lines.append(f"- Result: {result_preview}")
            lines.append("")
            tool_idx += 1

    lines.append("</details>")
    lines.append("")
    return "\n".join(lines)


def _validate_python_code(code: str) -> str:
    """Validate Python code using system validator."""
    from program_trader import validate_strategy_code

    result = validate_strategy_code(code)
    if result.is_valid:
        if result.warnings:
            return f"Syntax OK. Warnings: {'; '.join(result.warnings)}"
        return "Syntax OK. Code structure is valid."
    else:
        return f"Validation failed: {'; '.join(result.errors)}"


def _test_run_code(db: Session, code: str, symbol: str) -> str:
    """Test run code with real market data."""
    try:
        from program_trader.executor import SandboxExecutor
        from program_trader.models import MarketData
        from program_trader.data_provider import DataProvider

        # Create data provider with test account
        # Note: account_id=0 has no real wallet, so we use simulated account data
        # Strategy code can still call data_provider methods to get market data
        data_provider = DataProvider(db=db, account_id=0, environment="mainnet")

        # Create MarketData object with simulated account data
        market_data = MarketData(
            available_balance=10000.0,  # Simulated balance for testing
            total_equity=10000.0,
            used_margin=0.0,
            margin_usage_percent=0.0,
            maintenance_margin=0.0,
            positions={},  # No positions in test mode
            trigger_symbol=symbol,
            trigger_type="signal",
            _data_provider=data_provider,
        )

        # Create executor and run
        executor = SandboxExecutor(timeout_seconds=10)
        result = executor.execute(code, market_data, {})

        if result.success:
            decision = result.decision
            # Handle both old (action) and new (operation) Decision formats
            action_str = "none"
            if decision:
                if hasattr(decision, 'operation'):
                    action_str = decision.operation
                elif hasattr(decision, 'action'):
                    action_str = decision.action.value if hasattr(decision.action, 'value') else str(decision.action)
            return json.dumps({
                "success": True,
                "decision": decision.to_dict() if decision else None,
                "message": f"Test passed! Decision: {action_str}"
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error_type": "ExecutionError",
                "error": result.error,
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc()[:500]
        }, indent=2)
