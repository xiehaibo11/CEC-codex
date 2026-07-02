"""Service-layer logic for the event-contract paper trader CRUD/stats API
(spec module 1). Keeps ``api/event_contract_routes.py`` a thin HTTP shell.

Validation and fingerprinting reuse the existing engine (no duplicated
analysis logic):

- ``event_contract_service._normalize_config`` validates the submitted
  strategy config (raises ``ValueError`` on anything malformed).
- ``event_contract_service._strategy_fingerprint`` hashes the normalized,
  window-independent config so two traders sharing a strategy share a
  fingerprint.

The trader's ``config`` column stores the *raw* submitted config (not the
normalized one) - ``services.event_contract.live_paper_trader`` merges it
with the trader's symbol/exchange/environment columns and re-normalizes on
every cycle, mirroring how this module derives stats.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from services.event_contract.backtest_stats import binomial_p_value, wilson_interval
from services.event_contract_service import event_contract_service

_SETTLED = "settled"
_OPEN_STATUSES = ("pending_entry", "open")


def create_paper_trader(
    db: Session,
    name: str,
    config: Dict[str, Any],
    stake_amount: float = 100.0,
    initial_balance: float = 10000.0,
) -> Dict[str, Any]:
    """Validate ``config``, compute its strategy fingerprint, and persist a
    new paper trader. Raises ``ValueError`` for an invalid config or a
    duplicate name (caller maps this to HTTP 400, matching this route
    file's existing convention)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")

    raw_config = dict(config or {})
    cfg = event_contract_service._normalize_config(dict(raw_config), prediction=True)
    fingerprint = event_contract_service._strategy_fingerprint(cfg)

    existing = db.query(EventContractPaperTrader).filter(EventContractPaperTrader.name == name).first()
    if existing is not None:
        raise ValueError(f"Paper trader name '{name}' already exists")

    stake_amount = float(stake_amount) if stake_amount is not None else 100.0
    initial_balance = float(initial_balance) if initial_balance is not None else 10000.0

    trader = EventContractPaperTrader(
        name=name,
        enabled=True,
        symbol=cfg["symbol"],
        exchange=cfg["exchange"],
        environment=cfg["environment"],
        config=json.dumps(raw_config, default=str),
        stake_amount=stake_amount,
        initial_balance=initial_balance,
        current_balance=initial_balance,
        strategy_fingerprint=fingerprint,
    )
    db.add(trader)
    db.commit()
    db.refresh(trader)
    return _trader_dict(trader)


def list_paper_traders(db: Session) -> List[Dict[str, Any]]:
    """All paper traders, each merged with its live stats (same shape as
    :func:`get_paper_trader_stats`)."""
    traders = db.query(EventContractPaperTrader).order_by(EventContractPaperTrader.id.asc()).all()
    result = []
    for trader in traders:
        item = _trader_dict(trader)
        item.update(_stats_for_trader(db, trader))
        result.append(item)
    return result


def set_paper_trader_enabled(db: Session, trader_id: int, enabled: bool) -> Dict[str, Any]:
    trader = _get_trader_or_raise(db, trader_id)
    trader.enabled = bool(enabled)
    db.commit()
    db.refresh(trader)
    return _trader_dict(trader)


def get_paper_trader_bets(
    db: Session, trader_id: int, limit: int = 50, offset: int = 0
) -> Dict[str, Any]:
    _get_trader_or_raise(db, trader_id)
    limit = min(max(int(limit or 50), 1), 500)
    offset = max(int(offset or 0), 0)

    total = (
        db.query(EventContractPaperBet)
        .filter(EventContractPaperBet.trader_id == trader_id)
        .count()
    )
    bets = (
        db.query(EventContractPaperBet)
        .filter(EventContractPaperBet.trader_id == trader_id)
        .order_by(EventContractPaperBet.decision_time.desc(), EventContractPaperBet.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "trader_id": trader_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "bets": [_bet_dict(bet) for bet in bets],
    }


def get_paper_trader_stats(db: Session, trader_id: int) -> Dict[str, Any]:
    trader = _get_trader_or_raise(db, trader_id)
    return _stats_for_trader(db, trader)


def _get_trader_or_raise(db: Session, trader_id: int) -> EventContractPaperTrader:
    trader = db.get(EventContractPaperTrader, trader_id)
    if trader is None:
        raise ValueError(f"Paper trader {trader_id} not found")
    return trader


def _trader_cfg(trader: EventContractPaperTrader) -> Dict[str, Any]:
    stored_config = json.loads(trader.config or "{}")
    base_config = {
        **stored_config,
        "symbol": trader.symbol,
        "exchange": trader.exchange,
        "environment": trader.environment,
    }
    return event_contract_service._normalize_config(dict(base_config), prediction=True)


def _break_even_win_rate(cfg: Dict[str, Any]) -> float:
    payout = float(cfg.get("win_payout_ratio", 0.8))
    fee_rate = float(cfg.get("fee_rate", 0.0))
    if payout <= -1:
        return 100.0
    return (1 + fee_rate) / (payout + 1) * 100


def _stats_for_trader(db: Session, trader: EventContractPaperTrader) -> Dict[str, Any]:
    bets = (
        db.query(EventContractPaperBet)
        .filter(EventContractPaperBet.trader_id == trader.id)
        .all()
    )
    settled = [bet for bet in bets if bet.status == _SETTLED]
    wins = sum(1 for bet in settled if bet.result == "win")
    losses = sum(1 for bet in settled if bet.result == "loss")
    draws = sum(1 for bet in settled if bet.result == "draw")
    decided = wins + losses

    decided_win_rate = round(wins / decided * 100, 2) if decided else 0
    ci_low, ci_high = wilson_interval(wins, decided)

    cfg = _trader_cfg(trader)
    break_even_win_rate = _break_even_win_rate(cfg)
    p_value = binomial_p_value(wins, decided, break_even_win_rate / 100)

    total_pnl = sum(bet.pnl or 0 for bet in settled)
    open_bets = sum(1 for bet in bets if bet.status in _OPEN_STATUSES)

    return {
        "trader_id": trader.id,
        "n_settled": len(settled),
        "decided": decided,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "decided_win_rate": decided_win_rate,
        "win_rate_ci_low": ci_low,
        "win_rate_ci_high": ci_high,
        "p_value_vs_breakeven": p_value,
        "break_even_win_rate": round(break_even_win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "current_balance": trader.current_balance,
        "stake_amount": trader.stake_amount,
        "open_bets": open_bets,
        "strategy_fingerprint": trader.strategy_fingerprint,
    }


def _trader_dict(trader: EventContractPaperTrader) -> Dict[str, Any]:
    return {
        "id": trader.id,
        "name": trader.name,
        "enabled": trader.enabled,
        "symbol": trader.symbol,
        "exchange": trader.exchange,
        "environment": trader.environment,
        "config": json.loads(trader.config or "{}"),
        "stake_amount": trader.stake_amount,
        "initial_balance": trader.initial_balance,
        "current_balance": trader.current_balance,
        "strategy_fingerprint": trader.strategy_fingerprint,
        "created_at": _iso(trader.created_at),
        "updated_at": _iso(trader.updated_at),
    }


def _bet_dict(bet: EventContractPaperBet) -> Dict[str, Any]:
    return {
        "id": bet.id,
        "trader_id": bet.trader_id,
        "direction": bet.direction,
        "status": bet.status,
        "decision_time": _iso(bet.decision_time),
        "entry_time": _iso(bet.entry_time),
        "entry_price": bet.entry_price,
        "expiry_time": _iso(bet.expiry_time),
        "expiry_price": bet.expiry_price,
        "result": bet.result,
        "pnl": bet.pnl,
        "stake": bet.stake,
        "payout_ratio": bet.payout_ratio,
        "market_state": bet.market_state,
        "signal_strength": bet.signal_strength,
        "reason": bet.reason,
        "analysis_snapshot": json.loads(bet.analysis_snapshot) if bet.analysis_snapshot else None,
        "created_at": _iso(bet.created_at),
        "updated_at": _iso(bet.updated_at),
    }


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()
