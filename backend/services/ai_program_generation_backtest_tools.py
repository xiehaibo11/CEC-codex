"""Backtest analysis tools for AI program generation."""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import AccountProgramBinding, BacktestResult, BacktestTriggerLog

logger = logging.getLogger(__name__)

def _get_backtest_history(db: Session, program_id: Optional[int], user_id: int, limit: int = 10) -> str:
    """Get backtest history for the current program."""
    try:
        if not program_id:
            return json.dumps({"error": "No program selected. This tool only works when editing an existing program."})

        # Find all bindings for this program (a program can have multiple bindings)
        bindings = db.query(AccountProgramBinding).filter(
            AccountProgramBinding.program_id == program_id,
            AccountProgramBinding.is_deleted != True
        ).all()

        if not bindings:
            return json.dumps({"error": "No binding found for this program. Run a backtest first."})

        binding_ids = [b.id for b in bindings]

        # Get backtest history from all bindings
        backtests = db.query(BacktestResult).filter(
            BacktestResult.binding_id.in_(binding_ids),
            BacktestResult.status == "completed"
        ).order_by(BacktestResult.created_at.desc()).limit(limit).all()

        if not backtests:
            return json.dumps({"error": "No backtest results found. Run a backtest first."})

        results = []
        for bt in backtests:
            results.append({
                "id": bt.id,
                "time_range": f"{bt.start_time.strftime('%Y-%m-%d %H:%M') if bt.start_time else 'N/A'} ~ {bt.end_time.strftime('%Y-%m-%d %H:%M') if bt.end_time else 'N/A'}",
                "initial_balance": bt.initial_balance,
                "final_equity": round(bt.final_equity, 2) if bt.final_equity else 0,
                "total_pnl": round(bt.total_pnl, 2) if bt.total_pnl else 0,
                "total_pnl_percent": round(bt.total_pnl_percent, 2) if bt.total_pnl_percent else 0,
                "max_drawdown_percent": round(bt.max_drawdown_percent, 2) if bt.max_drawdown_percent else 0,
                "total_triggers": bt.total_triggers,
                "total_trades": bt.total_trades,  # Closed trades count
                "winning_trades": bt.winning_trades,  # TP count
                "losing_trades": bt.losing_trades,  # SL count
                "win_rate": round(bt.win_rate, 2) if bt.win_rate else 0,  # Already 0-100 scale
                "profit_factor": round(bt.profit_factor, 2) if bt.profit_factor else 0,
                "created_at": bt.created_at.strftime('%Y-%m-%d %H:%M') if bt.created_at else None
            })

        return json.dumps({
            "note": "Use these official stats directly. Do NOT recalculate from trigger list.",
            "backtests": results
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def _get_trigger_list(db: Session, backtest_id: int) -> str:
    """Get trigger summary list for a backtest."""
    try:
        triggers = db.query(BacktestTriggerLog).filter(
            BacktestTriggerLog.backtest_id == backtest_id
        ).order_by(BacktestTriggerLog.trigger_index).all()

        if not triggers:
            return json.dumps({"error": f"No triggers found for backtest {backtest_id}"})

        results = []
        for t in triggers:
            pnl = t.realized_pnl or 0
            results.append({
                "index": t.trigger_index,
                "time": t.trigger_time.strftime('%Y-%m-%d %H:%M:%S') if t.trigger_time else None,
                "type": t.trigger_type,
                "symbol": t.symbol,
                "action": t.decision_action,
                "side": t.decision_side,
                "size": round(t.decision_size, 4) if t.decision_size else None,
                "equity": f"${t.equity_before:.2f} -> ${t.equity_after:.2f}" if t.equity_before and t.equity_after else None,
                "pnl": round(pnl, 2) if pnl != 0 else None,
                "reason": t.decision_reason[:80] if t.decision_reason else None
            })

        return json.dumps({"total": len(results), "triggers": results}, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def _get_trigger_details(db: Session, backtest_id: int, indexes: List[int], fields: List[str] = None) -> str:
    """Get detailed info for specific triggers."""
    try:
        if not indexes:
            return json.dumps({"error": "indexes is required"})

        # Default to all fields
        if not fields:
            fields = ["summary", "input", "output", "queries", "logs"]

        triggers = db.query(BacktestTriggerLog).filter(
            BacktestTriggerLog.backtest_id == backtest_id,
            BacktestTriggerLog.trigger_index.in_(indexes)
        ).order_by(BacktestTriggerLog.trigger_index).all()

        if not triggers:
            return json.dumps({"error": f"No triggers found for indexes {indexes}"})

        results = []
        for t in triggers:
            detail = {"index": t.trigger_index}

            if "summary" in fields:
                detail["summary"] = {
                    "time": t.trigger_time.strftime('%Y-%m-%d %H:%M:%S') if t.trigger_time else None,
                    "type": t.trigger_type,
                    "symbol": t.symbol,
                    "action": t.decision_action,
                    "side": t.decision_side,
                    "size": t.decision_size,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "equity_before": t.equity_before,
                    "equity_after": t.equity_after,
                    "unrealized_pnl": t.unrealized_pnl,
                    "realized_pnl": t.realized_pnl,
                    "fee": t.fee,
                    "reason": t.decision_reason
                }

            if "input" in fields and t.decision_input:
                try:
                    detail["input"] = json.loads(t.decision_input)
                except:
                    detail["input"] = t.decision_input

            if "output" in fields and t.decision_output:
                try:
                    detail["output"] = json.loads(t.decision_output)
                except:
                    detail["output"] = t.decision_output

            if "queries" in fields and t.data_queries:
                try:
                    detail["queries"] = json.loads(t.data_queries)
                except:
                    detail["queries"] = t.data_queries

            if "logs" in fields and t.execution_logs:
                try:
                    detail["logs"] = json.loads(t.execution_logs)
                except:
                    detail["logs"] = t.execution_logs

            results.append(detail)

        return json.dumps({"triggers": results}, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def _quick_verify_strategy(
    db: Session,
    code: str,
    exchange: str,
    signal_pool_id: Optional[int] = None,
    scheduled_interval_minutes: Optional[int] = None,
    symbol: str = "BTC",
    hours: int = 168
) -> str:
    """
    Quick verify strategy code on historical data without storing results.
    Reuses ProgramBacktestEngine for accurate simulation.
    Returns core metrics from BacktestResult for AI analysis.
    """
    from backtest import BacktestConfig, ProgramBacktestEngine
    from datetime import datetime, timezone

    try:
        # Must have at least one trigger source
        if signal_pool_id is None and scheduled_interval_minutes is None:
            return json.dumps({"error": "Must specify signal_pool_id and/or scheduled_interval_minutes"})

        # Calculate time range (UTC)
        end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_time_ms = end_time_ms - (hours * 60 * 60 * 1000)

        # Build config - support combined triggers
        signal_pool_ids = [signal_pool_id] if signal_pool_id else []
        scheduled_interval_sec = scheduled_interval_minutes * 60 if scheduled_interval_minutes else None

        # Get symbols from signal pool if available
        symbols = [symbol]
        if signal_pool_id:
            from database.models import SignalPool
            pool = db.query(SignalPool).filter(SignalPool.id == signal_pool_id, SignalPool.is_deleted != True).first()
            if pool and pool.symbols:
                pool_symbols = pool.symbols
                if isinstance(pool_symbols, str):
                    pool_symbols = json.loads(pool_symbols)
                if pool_symbols:
                    symbols = pool_symbols

        config = BacktestConfig(
            code=code,
            signal_pool_ids=signal_pool_ids,
            symbols=symbols,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            scheduled_interval_sec=scheduled_interval_sec,
            initial_balance=10000.0,
            slippage_percent=0.05,
            fee_rate=0.035,
            exchange=exchange,
        )

        # Run backtest using existing engine (no DB storage)
        engine = ProgramBacktestEngine(db)
        result = engine.run(config)

        if not result.success:
            return json.dumps({"error": result.error or "Backtest failed"})

        # Extract sample trades (max 3)
        sample_trades = []
        for trade in result.trades[:3]:
            time_str = datetime.utcfromtimestamp(trade.timestamp / 1000).strftime('%Y-%m-%d %H:%M')
            sample_trades.append({
                "time": time_str,
                "action": trade.operation,
                "symbol": trade.symbol,
                "side": trade.side,
                "pnl": round(trade.pnl, 2) if trade.pnl else None,
                "reason": trade.reason[:50] if trade.reason else ''
            })

        # Return core metrics from BacktestResult
        return json.dumps({
            "success": True,
            "duration_hours": hours,
            "exchange": exchange,
            "trigger_config": {
                "signal_pool_id": signal_pool_id,
                "scheduled_interval_minutes": scheduled_interval_minutes
            },
            "triggers": {
                "total": result.total_triggers,
                "signal": result.signal_triggers,
                "scheduled": result.scheduled_triggers
            },
            "performance": {
                "total_pnl": round(result.total_pnl, 2),
                "total_pnl_percent": round(result.total_pnl_percent, 2),
                "max_drawdown_percent": round(result.max_drawdown_percent, 2),
                "sharpe_ratio": round(result.sharpe_ratio, 2) if result.sharpe_ratio else None
            },
            "trades": {
                "total": result.total_trades,
                "winning": result.winning_trades,
                "losing": result.losing_trades,
                "win_rate": round(result.win_rate, 1),
                "profit_factor": round(result.profit_factor, 2) if result.profit_factor else None
            },
            "sample_trades": sample_trades
        })

    except Exception as e:
        logger.error(f"Quick verify strategy error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
