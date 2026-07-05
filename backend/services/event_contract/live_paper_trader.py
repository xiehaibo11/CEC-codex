"""Live forward-testing paper trading cycle for event contracts (spec module 1).

Runs on a 60-second scheduler tick. For every enabled ``EventContractPaperTrader``
it walks a strict three-phase cycle over live 1m bars:

1. **Settle** - ``open`` bets whose ``expiry_time`` has passed get resolved off the
   1m bar whose OPEN timestamp matches (or is the first bar within
   ``max_expiry_lag_seconds`` of) the expiry epoch.
2. **Fill entry** - ``pending_entry`` bets get their strike price once the next 1m
   bar has printed: entry_price/time = that bar's open, expiry_time = entry_time +
   expiry_minutes.
3. **Decide** - if the trader has no outstanding bet and the latest closed 1m bar is
   newer than its last decision, ``event_contract_service.predict`` is consulted; an
   ``allow_trade`` long/short verdict opens a new ``pending_entry`` bet.

``event_contract_service.predict`` is reused as-is (no duplicated analysis logic).
Exceptions from predict are caught per-trader so one bad config never stalls the
cycle for the rest of the fleet.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from services.event_contract.constants import PERIOD_SECONDS
from services.event_contract_service import event_contract_service

logger = logging.getLogger(__name__)

EVENT_PAPER_TRADER_JOB_ID = "event_paper_trader_cycle"

# The paper trader only ever looks at 1m bars, regardless of any period a trader's
# stored config might carry from a backtest run it was cloned from.
_PERIOD = "1m"
_INTERVAL = PERIOD_SECONDS[_PERIOD]

# How far back to pull 1m bars for the settle/entry-fill phases when a trader has no
# outstanding bets to anchor the window on. One hour is comfortably more than the
# single "latest closed bar" lookup those phases need.
_DEFAULT_LOOKBACK_SECONDS = 3600

# Bet ids we've already logged a "no expiry bar past tolerance" warning for. The spec
# calls for warning once per stuck bet rather than every 60s cycle forever. Bounded so
# a long-running process doesn't accumulate this set unboundedly.
_WARNED_BET_IDS: set[int] = set()
_WARNED_BET_IDS_MAX = 1000


def _rollback_safely(session: Session) -> None:
    """Roll back the shared session without letting rollback itself raise.

    On Postgres a failed statement aborts the transaction; every subsequent
    statement on that connection (including for the next trader in this cycle)
    fails with InFailedSqlTransaction until a rollback happens. Call this at the
    top of every except block that might follow a failed DB statement.
    """
    try:
        session.rollback()
    except Exception:
        logger.exception("[EventPaperTrader] session.rollback() itself failed")


def run_live_paper_cycle(now_ts: Optional[int] = None, db: Optional[Session] = None) -> Dict[str, int]:
    """One cycle over all enabled paper traders.

    Injectable ``now_ts``/``db`` for tests. ``db`` defaults to a fresh
    ``SessionLocal`` that is closed before returning.

    Each trader commits (or rolls back) independently: a failure in one
    trader's cycle must never wipe another trader's already-staged,
    same-cycle work (settlements, fills, balance updates, opened bets) that
    shares this session. Per-trader counters are only folded into the
    returned totals after that trader's commit succeeds; a failed trader
    only ever contributes to ``errors``.
    """
    resolved_now = int(now_ts) if now_ts is not None else int(datetime.now(timezone.utc).timestamp())
    counters = {"settled": 0, "entries_filled": 0, "decisions": 0, "bets_opened": 0, "errors": 0}

    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        traders = (
            session.query(EventContractPaperTrader)
            .filter(EventContractPaperTrader.enabled.is_(True))
            .all()
        )
        for trader in traders:
            trader_counters = {"settled": 0, "entries_filled": 0, "decisions": 0, "bets_opened": 0}
            try:
                _run_trader_cycle(session, trader, resolved_now, trader_counters)
                session.commit()
                for key, value in trader_counters.items():
                    counters[key] += value
            except Exception:
                _rollback_safely(session)
                counters["errors"] += 1
                logger.exception(
                    "[EventPaperTrader] cycle failed for trader %s (%s)", trader.id, trader.name
                )
    finally:
        if owns_session:
            session.close()
    return counters


def _run_trader_cycle(
    session: Session, trader: EventContractPaperTrader, now_ts: int, counters: Dict[str, int]
) -> None:
    stored_config = json.loads(trader.config or "{}")
    base_config = {
        **stored_config,
        "symbol": trader.symbol,
        "exchange": trader.exchange,
        "environment": trader.environment,
    }
    # The cycle runs without a user context; CoinGlass-enabled strategies need
    # their key injected the same way authenticated requests get it.
    if base_config.get("enable_coinglass_features") and not base_config.get("_coinglass_api_key"):
        from api.coinglass.keys import resolve_background_coinglass_key

        api_key, key_source = resolve_background_coinglass_key(session)
        if api_key:
            base_config["_coinglass_api_key"] = api_key
            base_config["_coinglass_key_source"] = key_source
    cfg = event_contract_service._normalize_config(dict(base_config), prediction=True)

    klines = _load_trader_klines(session, trader, now_ts)
    ts_to_index = {item["timestamp"]: idx for idx, item in enumerate(klines)}

    _settle_due_bets(trader, cfg, klines, ts_to_index, now_ts, counters)
    _fill_pending_entries(trader, cfg, klines, counters)
    _maybe_decide(session, trader, cfg, base_config, klines, now_ts, counters)


def _load_trader_klines(
    session: Session, trader: EventContractPaperTrader, now_ts: int
) -> List[Dict[str, Any]]:
    candidates = [now_ts - _DEFAULT_LOOKBACK_SECONDS]
    for bet in trader.bets:
        if bet.status == "pending_entry" and bet.decision_time is not None:
            candidates.append(_epoch(bet.decision_time))
        elif bet.status == "open" and bet.expiry_time is not None:
            candidates.append(_epoch(bet.expiry_time))
    start_ts = min(candidates) - _INTERVAL
    return event_contract_service._load_klines(
        session, trader.exchange, trader.symbol, _PERIOD, start_ts, now_ts, trader.environment
    )


def _settle_due_bets(
    trader: EventContractPaperTrader,
    cfg: Dict[str, Any],
    klines: List[Dict[str, Any]],
    ts_to_index: Dict[int, int],
    now_ts: int,
    counters: Dict[str, int],
) -> None:
    due_bets = [
        bet
        for bet in trader.bets
        if bet.status == "open" and bet.expiry_time is not None and _epoch(bet.expiry_time) <= now_ts
    ]
    for bet in due_bets:
        expiry_ts = _epoch(bet.expiry_time)
        idx, _lag = event_contract_service._resolve_expiry_index(klines, ts_to_index, expiry_ts, cfg)
        if idx is None:
            elapsed = now_ts - expiry_ts
            if elapsed > cfg["max_expiry_lag_seconds"] and bet.id not in _WARNED_BET_IDS:
                logger.warning(
                    "[EventPaperTrader] trader %s bet %s: no expiry bar for expiry_ts=%s "
                    "after %ss (tolerance %ss) - leaving bet open",
                    trader.id, bet.id, expiry_ts, elapsed, cfg["max_expiry_lag_seconds"],
                )
                if len(_WARNED_BET_IDS) > _WARNED_BET_IDS_MAX:
                    _WARNED_BET_IDS.clear()
                _WARNED_BET_IDS.add(bet.id)
            continue

        expiry_price = klines[idx]["open"]
        result = event_contract_service._settle_event_contract(
            bet.direction, bet.entry_price, expiry_price, cfg["draw_result"]
        )
        fee = bet.stake * cfg["fee_rate"]
        if result == "win":
            pnl = bet.stake * bet.payout_ratio - fee
        elif result == "draw":
            pnl = -fee
        else:
            pnl = -bet.stake - fee

        bet.expiry_price = expiry_price
        bet.result = result
        bet.pnl = pnl
        bet.status = "settled"
        trader.current_balance = (trader.current_balance or 0) + pnl
        counters["settled"] += 1


def _fill_pending_entries(
    trader: EventContractPaperTrader,
    cfg: Dict[str, Any],
    klines: List[Dict[str, Any]],
    counters: Dict[str, int],
) -> None:
    pending_bets = [bet for bet in trader.bets if bet.status == "pending_entry"]
    for bet in pending_bets:
        decision_ts = _epoch(bet.decision_time)
        idx = event_contract_service._first_index_at_or_after(klines, decision_ts)
        if idx is None:
            continue
        bar = klines[idx]
        raw_entry_price = bar["open"]
        slippage_bps = float(cfg.get("slippage_bps") or 0)
        bet.entry_price = event_contract_service._apply_slippage(raw_entry_price, bet.direction, slippage_bps)
        bet.entry_time = _naive_utc(bar["timestamp"])
        bet.expiry_time = _naive_utc(bar["timestamp"] + cfg["expiry_minutes"] * 60)
        bet.status = "open"
        counters["entries_filled"] += 1


def _maybe_decide(
    session: Session,
    trader: EventContractPaperTrader,
    cfg: Dict[str, Any],
    base_config: Dict[str, Any],
    klines: List[Dict[str, Any]],
    now_ts: int,
    counters: Dict[str, int],
) -> None:
    # Non-overlap: never run a new decision while a bet is still awaiting entry
    # or settlement (statuses may have just changed above, so re-read fresh).
    if any(bet.status in ("pending_entry", "open") for bet in trader.bets):
        return

    closed_bars = [item for item in klines if item["timestamp"] + _INTERVAL <= now_ts]
    if not closed_bars:
        return
    latest_bar = max(closed_bars, key=lambda item: item["timestamp"])
    decision_ts = latest_bar["timestamp"] + _INTERVAL

    last_bet = max(trader.bets, key=lambda bet: bet.decision_time) if trader.bets else None
    if last_bet is not None and decision_ts <= _epoch(last_bet.decision_time):
        return

    if not event_contract_service._session_allows(decision_ts, cfg["allowed_utc_hours"]):
        return

    try:
        result = event_contract_service.predict(session, dict(base_config))
    except Exception as exc:  # noqa: BLE001 - one trader's failure must not stall the fleet
        # Re-raise so the per-trader try/except in run_live_paper_cycle rolls back
        # and counts the error exactly once. This trader's earlier staged phases
        # (settle/fill from THIS trader, same cycle) are discarded along with it -
        # single-trader atomicity - but since those increments only ever live in
        # this trader's local counters dict (merged into the cycle totals after a
        # successful commit), they are correctly never counted as persisted.
        logger.error(
            "[EventPaperTrader] predict failed for trader %s (%s): %s", trader.id, trader.name, exc
        )
        raise

    counters["decisions"] += 1

    best_action = result.get("best_action")
    if result.get("allow_trade") and best_action in ("long", "short"):
        snapshot = {
            key: value
            for key, value in result.items()
            if key not in ("similar_patterns", "data_quality")
        }
        bet = EventContractPaperBet(
            trader_id=trader.id,
            direction=best_action,
            status="pending_entry",
            decision_time=_naive_utc(decision_ts),
            stake=trader.stake_amount,
            payout_ratio=cfg["win_payout_ratio"],
            market_state=result.get("market_state"),
            signal_strength=result.get("signal_strength"),
            reason=result.get("reason"),
            analysis_snapshot=json.dumps(snapshot, default=str),
        )
        session.add(bet)
        counters["bets_opened"] += 1


def _epoch(value: Any) -> int:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _naive_utc(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
