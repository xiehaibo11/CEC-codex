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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.event_contract import (
    EventContractBacktestRun,
    EventContractPaperBet,
    EventContractPaperTrader,
)
from services.event_contract.backtest_stats import binomial_p_value, wilson_interval
from services.event_contract.execution import resolve_event_execution_adapter
from services.event_contract.production_policy import normalize_production_config
from services.event_contract_service import event_contract_service

_SETTLED = "settled"
_OPEN_STATUSES = ("pending_entry", "open")

# Bounded recency scan when matching a fingerprint against stored run summaries
# (mirrors rolling_validation's fallback path; works on any backend).
_VALIDATED_RUN_LOOKUP_LIMIT = 500

# Fragile-edge ceiling: share of trades whose outcome flips if the venue
# settlement print differs 5bps from our kline source. Run 2036 sat at 41.3% -
# an edge that thin lives inside microstructure noise and does not survive
# real execution.
_MAX_BPS5_FLIP_PCT = 25.0

# Miscalibration ceiling on the run's own probability quality. A well-behaved
# binary predictor sits near 0.20-0.25; run 2036 scored 0.655 because it
# reported the momentum-vote probability for bets that faded the momentum.
_MAX_BRIER_SCORE = 0.30


def _run_summary_deployable(summary: Dict[str, Any]) -> bool:
    """A run counts as deploy evidence only if it is significant vs break-even
    AND not disqualified by its own fragility/calibration diagnostics."""
    if not summary.get("significant_vs_breakeven"):
        return False
    sensitivity = summary.get("settlement_sensitivity") or {}
    bps5 = sensitivity.get("bps_5")
    if bps5 is not None and float(bps5) > _MAX_BPS5_FLIP_PCT:
        return False
    calibration = summary.get("calibration_report") or {}
    brier = calibration.get("brier_score")
    if calibration.get("status") == "ok" and brier is not None and float(brier) > _MAX_BRIER_SCORE:
        return False
    return True


def _find_validated_run(db: Session, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Most recent completed/partial backtest run whose summary carries this
    exact strategy fingerprint AND passes :func:`_run_summary_deployable`.

    This is the deploy gate: forward-testing a config that was never itself
    backtested tells you nothing about the validated strategy (trader #2
    shipped exactly that way and bled)."""
    try:
        rows = (
            db.query(EventContractBacktestRun)
            .filter(EventContractBacktestRun.status.in_(("completed", "partial")))
            .order_by(EventContractBacktestRun.id.desc())
            .limit(_VALIDATED_RUN_LOOKUP_LIMIT)
            .all()
        )
    except Exception:
        db.rollback()
        return None
    for row in rows:
        try:
            summary = json.loads(row.summary or "{}")
        except (TypeError, ValueError):
            continue
        if summary.get("strategy_fingerprint") != fingerprint:
            continue
        if _run_summary_deployable(summary):
            return {"run_id": row.id, "decided_win_rate": summary.get("decided_win_rate")}
    return None


def create_paper_trader(
    db: Session,
    name: str,
    config: Dict[str, Any],
    stake_amount: float = 100.0,
    initial_balance: float = 10000.0,
    allow_unvalidated: bool = False,
) -> Dict[str, Any]:
    """Validate ``config``, compute its strategy fingerprint, and persist a
    new paper trader. Raises ``ValueError`` for an invalid config or a
    duplicate name (caller maps this to HTTP 400, matching this route
    file's existing convention).

    Unless ``allow_unvalidated`` is set, the config's fingerprint must have at
    least one completed backtest run that is significant vs break-even."""
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")

    raw_config = normalize_production_config(config)
    adapter = resolve_event_execution_adapter(raw_config["execution_mode"])
    if raw_config["execution_mode"] == "live" and not adapter.capabilities.get("open"):
        raise ValueError(
            "live_event_contract_adapter_unavailable: Live event-contract execution cannot be enabled yet"
        )
    cfg = event_contract_service._normalize_config(dict(raw_config), prediction=True)
    fingerprint = event_contract_service._strategy_fingerprint(cfg)

    if not allow_unvalidated and _find_validated_run(db, fingerprint) is None:
        raise ValueError(
            f"Strategy fingerprint {fingerprint} has no completed backtest run that is "
            "significant vs break-even AND passes the fragility (settlement bps_5 <= 25%) "
            "and calibration (Brier <= 0.30) checks. Backtest this exact config first "
            "(fingerprints must match), or pass allow_unvalidated=true to deploy it as "
            "experimental."
        )

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
        execution_mode=raw_config["execution_mode"],
        leverage=raw_config["leverage"],
        trade_margin=raw_config["trade_margin"],
        max_daily_trades=raw_config["max_daily_trades"],
        profit_target_multiplier=raw_config["profit_target_multiplier"],
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
    if enabled:
        stored_config = json.loads(trader.config or "{}")
        if "signal_mode" not in stored_config:
            raise ValueError(
                "Legacy event-contract trader has no explicit signal_mode; recreate it with trend_follow"
            )
        normalize_production_config(stored_config)
        execution_mode = stored_config.get("execution_mode") or trader.execution_mode or "paper"
        adapter = resolve_event_execution_adapter(execution_mode)
        if execution_mode == "live" and not adapter.capabilities.get("open"):
            raise ValueError(
                "live_event_contract_adapter_unavailable: Live event-contract execution cannot be enabled yet"
            )
    trader.enabled = bool(enabled)
    db.commit()
    db.refresh(trader)
    return _trader_dict(trader)


def update_paper_trader_stake(db: Session, trader_id: int, stake_amount: float) -> Dict[str, Any]:
    """Change the flat per-bet stake. Sizing only - never touches strategy
    config/fingerprint, so it doesn't affect rolling-validation continuity or
    the sample count needed to statistically validate the edge itself."""
    if stake_amount <= 0:
        raise ValueError("stake_amount must be positive")
    trader = _get_trader_or_raise(db, trader_id)
    if stake_amount > trader.current_balance:
        raise ValueError(
            f"stake_amount {stake_amount} exceeds current balance {trader.current_balance}"
        )
    trader.stake_amount = stake_amount
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


def get_paper_trader_daily_stats(
    db: Session,
    trader_id: int,
    tz_offset_minutes: int = 480,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Customer-doc section-4 daily panel: stats for TODAY only, where "today"
    is the current calendar day in the requested timezone (default UTC+8) and
    resets at local midnight.

    A bet belongs to today when its SETTLEMENT landed inside the local day
    (``status == settled`` with ``expiry_time`` in the window), while
    ``opened_today`` counts bets whose ``decision_time`` landed inside it
    regardless of status - the customer's "daily total bets" is opened-today.

    ``now`` is naive UTC and injectable so tests don't depend on wall-clock
    (mirroring the auto-pause timestamp injection)."""
    _get_trader_or_raise(db, trader_id)

    if now is None:
        now = datetime.utcnow()
    offset = timedelta(minutes=int(tz_offset_minutes))
    local_now = now + offset
    day_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = day_start_local - offset
    day_end_utc = day_start_utc + timedelta(days=1)

    opened_today = (
        db.query(EventContractPaperBet)
        .filter(
            EventContractPaperBet.trader_id == trader_id,
            EventContractPaperBet.decision_time >= day_start_utc,
            EventContractPaperBet.decision_time < day_end_utc,
        )
        .count()
    )
    settled = (
        db.query(EventContractPaperBet)
        .filter(
            EventContractPaperBet.trader_id == trader_id,
            EventContractPaperBet.status == _SETTLED,
            EventContractPaperBet.expiry_time >= day_start_utc,
            EventContractPaperBet.expiry_time < day_end_utc,
        )
        .all()
    )

    wins = sum(1 for bet in settled if bet.result == "win")
    losses = sum(1 for bet in settled if bet.result == "loss")
    draws = sum(1 for bet in settled if bet.result == "draw")
    decided = wins + losses

    win_amount = sum(bet.pnl for bet in settled if (bet.pnl or 0) > 0)
    loss_amount = abs(sum(bet.pnl for bet in settled if (bet.pnl or 0) < 0))
    net_pnl = sum(bet.pnl or 0 for bet in settled)

    return {
        "trader_id": trader_id,
        "date": day_start_local.strftime("%Y-%m-%d"),
        "tz_offset_minutes": int(tz_offset_minutes),
        "opened_today": opened_today,
        "settled_today": len(settled),
        "wins": wins,
        "win_amount": round(win_amount, 2),
        "losses": losses,
        "loss_amount": round(loss_amount, 2),
        "draws": draws,
        "win_rate_pct": round(wins / decided * 100, 2) if decided else 0,
        "loss_rate_pct": round(losses / decided * 100, 2) if decided else 0,
        "net_pnl": round(net_pnl, 2),
    }


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
    try:
        production_config = normalize_production_config(dict(base_config))
    except ValueError:
        # Historical traders remain readable for audit/statistics, but the
        # runtime enable path rejects them. Do not turn a legacy row into a
        # 500 response merely because its strategy is no longer deployable.
        production_config = base_config
    return event_contract_service._normalize_config(dict(production_config), prediction=True)


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
    stored_config = json.loads(trader.config or "{}")
    try:
        policy_config = normalize_production_config(stored_config)
        policy_error = None
    except ValueError as exc:
        policy_config = stored_config
        policy_error = str(exc)
    if policy_error is None and "signal_mode" not in stored_config:
        policy_config = stored_config
        policy_error = "Legacy event-contract trader has no explicit signal_mode"
    if policy_error is None:
        # The execution column is authoritative for new rows; keep the JSON
        # response internally consistent when a migration filled its default.
        policy_config["execution_mode"] = trader.execution_mode or "paper"
    return {
        "id": trader.id,
        "name": trader.name,
        "enabled": trader.enabled,
        "symbol": trader.symbol,
        "exchange": trader.exchange,
        "environment": trader.environment,
        "config": policy_config,
        "policy_error": policy_error,
        "stake_amount": trader.stake_amount,
        "initial_balance": trader.initial_balance,
        "current_balance": trader.current_balance,
        "strategy_fingerprint": trader.strategy_fingerprint,
        "execution_mode": trader.execution_mode or "paper",
        "execution_capabilities": resolve_event_execution_adapter(
            trader.execution_mode or "paper"
        ).capabilities,
        "daily_trade_limit": trader.max_daily_trades or 10,
        "profit_target_reached": bool(
            stored_config.get("profit_target")
            or float(trader.current_balance or 0)
            >= float(trader.initial_balance or 0) * float(trader.profit_target_multiplier or 2)
        ),
        "stop_reason": stored_config.get("profit_target")
        or stored_config.get("auto_pause")
        or stored_config.get("policy_block"),
        "leverage": trader.leverage,
        "trade_margin": trader.trade_margin,
        "max_daily_trades": trader.max_daily_trades,
        "profit_target_multiplier": trader.profit_target_multiplier,
        "last_decision_time": _iso(trader.last_decision_time),
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
