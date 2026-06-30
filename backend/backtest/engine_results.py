"""
Result/statistics calculation for the Program Backtest Engine.

Aggregates closed trades, equity curve and trigger counts into a BacktestResult
(PnL, win rate, profit factor, drawdown, Sharpe, etc.). Mixed into
ProgramBacktestEngine.
"""

import logging
from typing import Dict, List, Any

from .models import BacktestConfig, TriggerEvent, BacktestResult, BacktestTradeRecord
from .virtual_account import VirtualAccount

logger = logging.getLogger(__name__)


class ResultCalculationMixin:
    """Computes summary statistics for a completed backtest run."""

    def _calculate_result(
        self,
        trades: List[BacktestTradeRecord],
        equity_curve: List[Dict[str, Any]],
        triggers: List[TriggerEvent],
        account: VirtualAccount,
        config: BacktestConfig,
    ) -> BacktestResult:
        """Calculate backtest statistics."""
        # Filter closed trades (with exit_price)
        closed_trades = [t for t in trades if t.exit_price is not None]

        # Basic counts
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]

        # PnL calculations
        total_pnl = sum(t.pnl for t in closed_trades)
        total_pnl_percent = (total_pnl / config.initial_balance * 100) if config.initial_balance > 0 else 0

        # Win rate
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        # Profit factor
        total_profit = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        # When total_loss is 0, profit_factor is undefined (use None to avoid JSON Infinity issue)
        profit_factor = (total_profit / total_loss) if total_loss > 0 else None

        # Average win/loss
        avg_win = (total_profit / len(winning_trades)) if winning_trades else 0
        avg_loss = (total_loss / len(losing_trades)) if losing_trades else 0

        # Largest win/loss
        largest_win = max((t.pnl for t in winning_trades), default=0)
        largest_loss = min((t.pnl for t in losing_trades), default=0)

        # Trigger counts
        signal_triggers = sum(1 for t in triggers if t.trigger_type == "signal")
        scheduled_triggers = sum(1 for t in triggers if t.trigger_type == "scheduled")

        # Sharpe ratio (simplified - annualized)
        sharpe_ratio = 0.0
        if equity_curve and len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                prev_eq = equity_curve[i-1]["equity"]
                curr_eq = equity_curve[i]["equity"]
                if prev_eq > 0:
                    returns.append((curr_eq - prev_eq) / prev_eq)

            if returns:
                import statistics
                mean_return = statistics.mean(returns)
                std_return = statistics.stdev(returns) if len(returns) > 1 else 0
                if std_return > 0:
                    # Annualize (assume daily returns, 252 trading days)
                    sharpe_ratio = (mean_return / std_return) * (252 ** 0.5)

        return BacktestResult(
            success=True,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            max_drawdown=account.max_drawdown,
            max_drawdown_percent=account.max_drawdown_percent * 100,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            total_triggers=len(triggers),
            signal_triggers=signal_triggers,
            scheduled_triggers=scheduled_triggers,
            equity_curve=equity_curve,
            trades=trades,
            trigger_log=triggers,
            start_time=config.start_time,
            end_time=config.end_time,
        )
