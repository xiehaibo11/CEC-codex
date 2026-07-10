"""Historical expected-value gate for event-contract decisions.

Every stratification of the deduplicated trade-log history (6867 decided
market events as of 2026-07-07) put the signal family at 42-52% - below the
55.6% break-even of a 0.8 payout. Configs that backtested above break-even
were the lucky tail of thousands of sibling runs. This module makes that
pooled evidence a hard input to each decision:

- ``estimate_historical_win_rate`` - deduplicated win rate of similar past
  trades (same symbol/direction/market_state), strictly before a cutoff so
  backtest replays cannot peek at their own future.
- ``check_ev_gate`` - allow a bet only when the Wilson lower bound of that
  estimate clears break-even on an adequate sample. "No demonstrated edge"
  and "demonstrated negative edge" both refuse.
- ``ev_gate_report`` - post-hoc audit for a finished backtest: how many of
  its trades the gate would have allowed, and how each group actually did.

Trades are deduplicated by (symbol, direction, entry_time): the same market
event replayed by many sibling backtest runs is one observation, not many.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.event_contract.backtest_stats import wilson_interval

DEFAULT_MIN_N = 50

# One row per distinct market event; portable across Postgres and SQLite.
_ESTIMATE_SQL = text(
    """
    SELECT t.result, COUNT(*) AS n
    FROM (
        SELECT MAX(id) AS id
        FROM event_contract_trade_logs
        WHERE symbol = :symbol
          AND direction = :direction
          AND market_state = :market_state
          AND result IN ('win', 'loss')
          AND entry_time < :cutoff
        GROUP BY symbol, direction, entry_time
    ) d
    JOIN event_contract_trade_logs t ON t.id = d.id
    GROUP BY t.result
    """
)


def estimate_historical_win_rate(
    db: Session,
    *,
    symbol: str,
    direction: str,
    market_state: str,
    cutoff: datetime,
) -> Dict[str, Any]:
    """Deduplicated decided-trade record for one (symbol, direction,
    market_state) cell, strictly before ``cutoff``. Returns counts plus a
    Wilson 95% interval in percent."""
    rows = db.execute(
        _ESTIMATE_SQL,
        {
            "symbol": symbol,
            "direction": direction,
            "market_state": market_state,
            "cutoff": cutoff,
        },
    ).all()
    counts = {result: int(n) for result, n in rows}
    wins = counts.get("win", 0)
    losses = counts.get("loss", 0)
    n = wins + losses
    ci_low, ci_high = wilson_interval(wins, n)
    return {
        "symbol": symbol,
        "direction": direction,
        "market_state": market_state,
        "cutoff": cutoff.isoformat(),
        "n": n,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / n * 100, 2) if n else 0.0,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def check_ev_gate(
    db: Session,
    *,
    symbol: str,
    direction: str,
    market_state: str,
    cutoff: datetime,
    break_even_pct: float,
    min_n: int = DEFAULT_MIN_N,
) -> Dict[str, Any]:
    """Allow only when history demonstrates positive expectancy: at least
    ``min_n`` deduplicated decided events AND the Wilson lower bound of their
    win rate at or above ``break_even_pct``."""
    estimate = estimate_historical_win_rate(
        db, symbol=symbol, direction=direction, market_state=market_state, cutoff=cutoff
    )
    if estimate["n"] < min_n:
        return {
            "allowed": False,
            "estimate": estimate,
            "reason": (
                f"EV门：同类历史交易样本不足（{estimate['n']} < {min_n}），"
                f"未证明超过盈亏平衡 {break_even_pct:.2f}% 的优势"
            ),
        }
    if estimate["ci_low"] < break_even_pct:
        return {
            "allowed": False,
            "estimate": estimate,
            "reason": (
                f"EV门：同类历史交易 {estimate['n']} 笔胜率 {estimate['win_rate']:.1f}%"
                f"（Wilson下界 {estimate['ci_low']:.1f}%）未达盈亏平衡 {break_even_pct:.2f}%"
            ),
        }
    return {
        "allowed": True,
        "estimate": estimate,
        "reason": (
            f"EV门通过：同类历史交易 {estimate['n']} 笔胜率 {estimate['win_rate']:.1f}%，"
            f"Wilson下界 {estimate['ci_low']:.1f}% ≥ 盈亏平衡 {break_even_pct:.2f}%"
        ),
    }


def _parse_entry_time(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def ev_gate_report(
    db: Session,
    trades: List[Dict[str, Any]],
    *,
    break_even_pct: float,
    min_n: int = DEFAULT_MIN_N,
) -> Dict[str, Any]:
    """Post-hoc audit of a finished backtest's decided trades against the
    gate, each evaluated with a leakage-safe cutoff at its own entry time.
    A run whose trades the gate mostly blocks is trading a family with no
    demonstrated edge, whatever its own headline win rate says."""
    allowed: List[str] = []
    blocked: List[str] = []
    skipped = 0
    for trade in trades:
        if trade.get("result") not in ("win", "loss"):
            continue
        cutoff = _parse_entry_time(trade.get("entry_time"))
        symbol = trade.get("symbol")
        direction = trade.get("direction")
        market_state = trade.get("market_state")
        if cutoff is None or not symbol or not direction or not market_state:
            skipped += 1
            continue
        verdict = check_ev_gate(
            db,
            symbol=symbol,
            direction=direction,
            market_state=market_state,
            cutoff=cutoff,
            break_even_pct=break_even_pct,
            min_n=min_n,
        )
        (allowed if verdict["allowed"] else blocked).append(trade["result"])

    def _win_rate(results: List[str]) -> Optional[float]:
        return round(results.count("win") / len(results) * 100, 2) if results else None

    return {
        "evaluated": len(allowed) + len(blocked),
        "skipped": skipped,
        "allowed": len(allowed),
        "blocked": len(blocked),
        "allowed_win_rate": _win_rate(allowed),
        "blocked_win_rate": _win_rate(blocked),
        "break_even_win_rate": round(break_even_pct, 2),
        "min_n": min_n,
    }
