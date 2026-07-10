"""Deterministic pre-trade risk guards shared by AI-decision executors.

Evidence that motivated them (Binance testnet, 2026-07-06): the scheduled LLM
repeated one bearish news thesis five times in three hours and every executed
sell realized a loss; meanwhile same-direction exposure stacked unbounded
until the post-hoc margin monitor force-closed positions. Neither failure
needs intelligence to prevent - both are pure hygiene:

1. **Loss-streak guard** - after N consecutive settled losses on the same
   (account, symbol, direction) within the lookback window, further opens in
   that direction are blocked. The thesis had its chances; wait for it to be
   right or for the window to pass.
2. **Exposure-cap guard** - once existing same-direction notional exceeds
   ``MAX_SAME_DIRECTION_EXPOSURE`` x equity, further adds are blocked. Risk
   monitors should be the backstop, not the exit strategy.

``hold``/``close`` are never blocked: reducing risk is always allowed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.trading import AIDecisionLog

logger = logging.getLogger(__name__)

# Block a direction after this many consecutive settled losses on it.
LOSS_STREAK_LIMIT = 2
# Only losses within this window count - an old streak should not gate a new regime.
LOSS_STREAK_LOOKBACK_HOURS = 24
# Existing same-direction notional (as a multiple of equity) above which adds are blocked.
MAX_SAME_DIRECTION_EXPOSURE = 2.0


def check_pre_trade_guards(
    db: Session,
    *,
    account_id: int,
    symbol: str,
    operation: str,
    positions: List[Dict[str, Any]],
    total_equity: float,
    now: Optional[datetime] = None,
    loss_streak_limit: int = LOSS_STREAK_LIMIT,
    lookback_hours: int = LOSS_STREAK_LOOKBACK_HOURS,
    max_exposure: float = MAX_SAME_DIRECTION_EXPOSURE,
) -> Dict[str, Any]:
    """Return ``{"allowed": bool, "reason": str}`` for one open/add decision.

    ``positions`` uses the executor's exchange-normalized shape: each item has
    ``coin``, ``szi`` (signed size) and ``position_value`` (notional)."""
    if operation not in ("buy", "sell"):
        return {"allowed": True, "reason": ""}

    resolved_now = now or datetime.utcnow()

    if total_equity <= 0:
        return {
            "allowed": False,
            "reason": "风控闸：账户权益为 0，禁止新增敞口",
        }

    streak = _recent_same_direction_losses(
        db, account_id, symbol, operation, resolved_now, lookback_hours, loss_streak_limit
    )
    if streak >= loss_streak_limit:
        return {
            "allowed": False,
            "reason": (
                f"风控闸：{symbol} {operation} 方向最近 {streak} 笔已结算交易连续亏损"
                f"（{lookback_hours}h 窗口内）。同一论点不再重复执行，等待新证据。"
            ),
        }

    exposure = _same_direction_notional(positions, symbol, operation)
    if exposure / total_equity >= max_exposure:
        return {
            "allowed": False,
            "reason": (
                f"风控闸：{symbol} 同方向敞口已达权益的 "
                f"{exposure / total_equity:.2f} 倍（上限 {max_exposure:.1f}），禁止加仓。"
            ),
        }

    # Rule patch from loss attribution (2026-07-08): 70% of settled losses
    # were adds onto existing same-direction exposure. Averaging into a
    # position that is currently under water is doubling down on a thesis
    # the market is already voting against.
    losing = _same_direction_losing_pnl(positions, symbol, operation)
    if losing < 0:
        return {
            "allowed": False,
            "reason": (
                f"风控闸：{symbol} 同方向持仓当前浮动亏损 {losing:.2f}，"
                "禁止对亏损持仓加仓。等持仓转正或先离场再评估。"
            ),
        }

    return {"allowed": True, "reason": ""}


def _same_direction_losing_pnl(
    positions: List[Dict[str, Any]], symbol: str, operation: str
) -> float:
    """Unrealized pnl of existing positions in the direction this operation
    would add to (0.0 when there is none or the venue omits the field)."""
    want_long = operation == "buy"
    total = 0.0
    for pos in positions or []:
        if str(pos.get("coin", "")).upper() != symbol.upper():
            continue
        szi = float(pos.get("szi") or 0)
        if szi == 0 or (szi > 0) != want_long:
            continue
        total += float(pos.get("unrealized_pnl") or 0)
    return total


def _recent_same_direction_losses(
    db: Session,
    account_id: int,
    symbol: str,
    operation: str,
    now: datetime,
    lookback_hours: int,
    limit: int,
) -> int:
    """Consecutive settled losses in this direction, counting back from the
    most recent settled decision. A win (or break-even) ends the streak."""
    rows = (
        db.query(AIDecisionLog.realized_pnl)
        .filter(
            AIDecisionLog.account_id == account_id,
            AIDecisionLog.symbol == symbol,
            AIDecisionLog.operation == operation,
            AIDecisionLog.executed == "true",
            AIDecisionLog.realized_pnl.isnot(None),
            AIDecisionLog.realized_pnl != 0,
            AIDecisionLog.decision_time >= now - timedelta(hours=lookback_hours),
            # Upper bound matters for historical replays (prompt backtests):
            # decisions AFTER the evaluated moment must not leak back in time.
            AIDecisionLog.decision_time <= now,
        )
        .order_by(AIDecisionLog.decision_time.desc())
        .limit(limit)
        .all()
    )
    streak = 0
    for (pnl,) in rows:
        if float(pnl) < 0:
            streak += 1
        else:
            break
    return streak


def _same_direction_notional(
    positions: List[Dict[str, Any]], symbol: str, operation: str
) -> float:
    """Existing notional in the direction this operation would add to."""
    want_long = operation == "buy"
    total = 0.0
    for pos in positions or []:
        if str(pos.get("coin", "")).upper() != symbol.upper():
            continue
        szi = float(pos.get("szi") or 0)
        if szi == 0:
            continue
        if (szi > 0) == want_long:
            total += abs(float(pos.get("position_value") or 0))
    return total
