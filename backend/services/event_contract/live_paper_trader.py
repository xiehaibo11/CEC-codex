"""Live forward-testing paper trading cycle for event contracts (spec module 1).

Runs on a 1-second scheduler tick. For every enabled ``EventContractPaperTrader``
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

from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from services.event_contract.backtest_stats import binomial_p_value
from services.event_contract.constants import PERIOD_SECONDS
from services.event_contract.execution import resolve_event_execution_adapter
from services.event_contract.production_policy import normalize_production_config
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

# Auto-pause kill switch defaults: once a trader has this many decided (win/loss)
# settled bets, a one-sided exact binomial test against the payout's break-even win
# rate runs after every settle phase. If the observed record is significantly BELOW
# break-even, the config's edge is considered falsified by forward data and the
# trader is disabled. Guards against overfit/unvalidated configs bleeding forever.
_AUTO_PAUSE_MIN_DECIDED = 12
_AUTO_PAUSE_ALPHA = 0.05

# Soft, self-recovering risk brakes checked at the top of the decide phase (settle
# and entry-fill are never paused, and unlike auto-pause nothing is written to the
# DB or config - these are transient states recomputed every cycle).
_COOLDOWN_LOSS_STREAK = 4  # consecutive settled losses that trigger the cooldown
_COOLDOWN_MINUTES = 60  # cooldown length, measured from the newest settled expiry
_DAILY_LOSS_CAP_PCT = 5.0  # max settled loss per UTC day, % of initial_balance

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
    """One cycle over enabled traders and disabled traders with open bets.

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
            .filter(
                or_(
                    EventContractPaperTrader.enabled.is_(True),
                    EventContractPaperTrader.bets.any(
                        EventContractPaperBet.status.in_(("pending_entry", "open"))
                    ),
                )
            )
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
    try:
        production_config = normalize_production_config(
            {
                **base_config,
                "execution_mode": trader.execution_mode or base_config.get("execution_mode", "paper"),
            }
        )
    except ValueError as exc:
        # Historical countertrend rows must not continue evaluating as
        # production traders. Their bets and backtest history remain intact.
        trader.enabled = False
        stored_config["policy_block"] = {
            "blocked_at": _naive_utc(now_ts).isoformat(),
            "reason": str(exc),
        }
        trader.config = json.dumps(stored_config, default=str)
        # A policy block stops new decisions but must not strand an already
        # accepted paper bet forever. Use the historical config only for
        # settlement/fill bookkeeping; the disabled trader never reaches the
        # decision phase below.
        try:
            cfg = event_contract_service._normalize_config(dict(base_config), prediction=True)
            klines = _load_trader_klines(session, trader, now_ts)
            ts_to_index = {item["timestamp"]: idx for idx, item in enumerate(klines)}
            _settle_due_bets(trader, cfg, klines, ts_to_index, now_ts, counters)
            _fill_pending_entries(trader, cfg, klines, counters)
        except Exception:  # noqa: BLE001 - policy block must remain non-fatal
            logger.exception(
                "[EventPaperTrader] blocked trader %s (%s): failed to finish outstanding bet",
                trader.id,
                trader.name,
            )
        logger.warning(
            "[EventPaperTrader] disabled trader %s (%s): production policy blocked it: %s",
            trader.id,
            trader.name,
            exc,
        )
        return
    base_config = {**base_config, **production_config}
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
    if not trader.enabled:
        # Disabled traders are serviced only to finish their outstanding
        # paper lifecycle. They are never allowed to create a new decision.
        return
    if _maybe_stop_at_profit_target(trader, stored_config, now_ts):
        return
    if _maybe_auto_pause(trader, cfg, stored_config, now_ts):
        return
    _maybe_decide(session, trader, cfg, base_config, stored_config, klines, now_ts, counters)


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


def _maybe_auto_pause(
    trader: EventContractPaperTrader,
    cfg: Dict[str, Any],
    stored_config: Dict[str, Any],
    now_ts: int,
) -> bool:
    """Disable the trader when its forward record statistically falsifies the
    edge: P(<= observed wins | decided, break-even win rate) below alpha.

    Only runs on a clean state (no pending/open bets) so the tested sample is
    exactly the settled record. Returns True when the trader was paused."""
    if not stored_config.get("auto_pause_enabled", True):
        return False
    if any(bet.status in ("pending_entry", "open") for bet in trader.bets):
        return False

    wins = sum(1 for bet in trader.bets if bet.status == "settled" and bet.result == "win")
    losses = sum(1 for bet in trader.bets if bet.status == "settled" and bet.result == "loss")
    decided = wins + losses
    min_decided = int(stored_config.get("auto_pause_min_decided", _AUTO_PAUSE_MIN_DECIDED))
    if decided < min_decided:
        return False

    payout = float(cfg["win_payout_ratio"])
    fee_rate = float(cfg["fee_rate"])
    if payout <= -1:
        return False
    break_even = (1 + fee_rate) / (payout + 1)
    # Lower tail P(X <= wins) via the existing upper-tail helper.
    p_value = 1.0 - binomial_p_value(wins + 1, decided, break_even)
    alpha = float(stored_config.get("auto_pause_alpha", _AUTO_PAUSE_ALPHA))
    if p_value >= alpha:
        return False

    trader.enabled = False
    stored_config["auto_pause"] = {
        "paused_at": _naive_utc(now_ts).isoformat(),
        "decided": decided,
        "wins": wins,
        "losses": losses,
        "p_value": round(p_value, 6),
        "break_even_win_rate": round(break_even * 100, 2),
        "reason": "forward win rate significantly below break-even",
    }
    trader.config = json.dumps(stored_config, default=str)
    logger.warning(
        "[EventPaperTrader] AUTO-PAUSE trader %s (%s): %s wins / %s decided, "
        "break-even %.2f%%, one-sided p=%.5f < %.2f - forward data falsifies the edge",
        trader.id, trader.name, wins, decided, break_even * 100, p_value, alpha,
    )
    return True


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


def _in_loss_cooldown(
    trader: EventContractPaperTrader, stored_config: Dict[str, Any], now_ts: int
) -> bool:
    """Soft brake: after ``cooldown_loss_streak`` consecutive settled losses, skip
    NEW decisions for ``cooldown_minutes`` measured from the newest settled bet's
    expiry_time. A win resets the streak (draws neither extend nor reset it) and
    the trader resumes on its own - transient state, nothing is persisted."""
    streak_limit = int(stored_config.get("cooldown_loss_streak", _COOLDOWN_LOSS_STREAK))
    if streak_limit <= 0:
        return False

    settled = sorted(
        (bet for bet in trader.bets if bet.status == "settled" and bet.expiry_time is not None),
        key=lambda bet: _epoch(bet.expiry_time),
        reverse=True,
    )
    streak = 0
    for bet in settled:
        if bet.result == "loss":
            streak += 1
            if streak >= streak_limit:
                break
        elif bet.result == "win":
            break
    if streak < streak_limit:
        return False

    cooldown_seconds = float(stored_config.get("cooldown_minutes", _COOLDOWN_MINUTES)) * 60
    cooldown_end = _epoch(settled[0].expiry_time) + cooldown_seconds
    if now_ts >= cooldown_end:
        return False

    logger.info(
        "[EventPaperTrader] trader %s (%s) in loss cooldown: %s consecutive losses "
        "(threshold %s), new decisions resume at %s UTC",
        trader.id, trader.name, streak, streak_limit, _naive_utc(int(cooldown_end)).isoformat(),
    )
    return True


def _daily_loss_stopped(
    trader: EventContractPaperTrader, stored_config: Dict[str, Any], now_ts: int
) -> bool:
    """Soft brake: once today's (UTC) settled pnl reaches a loss of the daily cap,
    skip NEW decisions for the rest of the UTC day. The absolute ``daily_loss_cap``
    (dollars) takes precedence when set; otherwise ``daily_loss_cap_pct`` percent
    of initial_balance applies. Transient state, nothing is persisted."""
    raw_abs_cap = stored_config.get("daily_loss_cap")
    if raw_abs_cap is not None:
        cap = float(raw_abs_cap)
    else:
        pct = float(stored_config.get("daily_loss_cap_pct", _DAILY_LOSS_CAP_PCT))
        initial = float(trader.initial_balance or 0)
        cap = initial * pct / 100.0
    if cap <= 0:
        return False

    day_start = now_ts - (now_ts % 86400)
    day_pnl = sum(
        float(bet.pnl or 0)
        for bet in trader.bets
        if bet.status == "settled"
        and bet.expiry_time is not None
        and day_start <= _epoch(bet.expiry_time) < day_start + 86400
    )
    if day_pnl > -cap:
        return False

    logger.info(
        "[EventPaperTrader] trader %s (%s) hit the daily loss stop: settled pnl "
        "today %.2f <= -%.2f, no new decisions until the next UTC day",
        trader.id, trader.name, day_pnl, cap,
    )
    return True


def _daily_opened_count(
    trader: EventContractPaperTrader, stored_config: Dict[str, Any], now_ts: int
) -> int:
    """Count decision bets inside the configured local calendar day."""
    offset_minutes = int(stored_config.get("timezone_offset_minutes", 480))
    local_now = now_ts + offset_minutes * 60
    local_day_start = local_now - (local_now % 86400)
    day_start = local_day_start - offset_minutes * 60
    day_end = day_start + 86400
    return sum(
        1
        for bet in trader.bets
        if bet.decision_time is not None and day_start <= _epoch(bet.decision_time) < day_end
    )


def _daily_trade_limit_reached(
    trader: EventContractPaperTrader, stored_config: Dict[str, Any], now_ts: int
) -> bool:
    limit = int(trader.max_daily_trades or stored_config.get("max_daily_trades", 10))
    if limit <= 0:
        return True
    opened = _daily_opened_count(trader, stored_config, now_ts)
    if opened < limit:
        return False
    logger.info(
        "[EventPaperTrader] trader %s (%s) reached daily trade limit %s/%s; waiting for next local day",
        trader.id,
        trader.name,
        opened,
        limit,
    )
    return True


def _target_win_rate_blocks(
    trader: EventContractPaperTrader, stored_config: Dict[str, Any]
) -> bool:
    target = float(stored_config.get("target_win_rate", 75))
    minimum = int(stored_config.get("target_min_trades", 10))
    settled = [bet for bet in trader.bets if bet.status == "settled"]
    wins = sum(1 for bet in settled if bet.result == "win")
    losses = sum(1 for bet in settled if bet.result == "loss")
    decided = wins + losses
    if decided < minimum:
        return False
    rate = wins / decided * 100 if decided else 0
    if rate >= target:
        return False
    logger.info(
        "[EventPaperTrader] trader %s (%s) below target win rate %.2f%% < %.2f%% after %s trades",
        trader.id,
        trader.name,
        rate,
        target,
        decided,
    )
    return True


def _maybe_stop_at_profit_target(
    trader: EventContractPaperTrader, stored_config: Dict[str, Any], now_ts: int
) -> bool:
    multiplier = float(
        trader.profit_target_multiplier
        or stored_config.get("profit_target_multiplier", 2.0)
    )
    initial = float(trader.initial_balance or 0)
    current = float(trader.current_balance or 0)
    if multiplier <= 1 or initial <= 0 or current < initial * multiplier:
        return False
    trader.enabled = False
    stored_config["profit_target"] = {
        "stopped_at": _naive_utc(now_ts).isoformat(),
        "initial_balance": initial,
        "final_balance": current,
        "multiplier": multiplier,
        "reason": "equity reached configured profit target; no new entries",
    }
    trader.config = json.dumps(stored_config, default=str)
    logger.warning(
        "[EventPaperTrader] trader %s (%s) stopped at profit target: %.2f >= %.2f",
        trader.id,
        trader.name,
        current,
        initial * multiplier,
    )
    return True


def _maybe_decide(
    session: Session,
    trader: EventContractPaperTrader,
    cfg: Dict[str, Any],
    base_config: Dict[str, Any],
    stored_config: Dict[str, Any],
    klines: List[Dict[str, Any]],
    now_ts: int,
    counters: Dict[str, int],
) -> None:
    # Non-overlap: never run a new decision while a bet is still awaiting entry
    # or settlement (statuses may have just changed above, so re-read fresh).
    if any(bet.status in ("pending_entry", "open") for bet in trader.bets):
        return

    if _in_loss_cooldown(trader, stored_config, now_ts):
        return
    if _daily_loss_stopped(trader, stored_config, now_ts):
        return
    if _daily_trade_limit_reached(trader, stored_config, now_ts):
        return
    if _target_win_rate_blocks(trader, stored_config):
        return

    closed_bars = [item for item in klines if item["timestamp"] + _INTERVAL <= now_ts]
    if not closed_bars:
        return
    latest_bar = max(closed_bars, key=lambda item: item["timestamp"])
    decision_ts = latest_bar["timestamp"] + _INTERVAL

    if trader.last_decision_time is not None and decision_ts <= _epoch(trader.last_decision_time):
        return

    last_bet = max(trader.bets, key=lambda bet: bet.decision_time) if trader.bets else None
    if last_bet is not None and decision_ts <= _epoch(last_bet.decision_time):
        return

    if not event_contract_service._session_allows(decision_ts, cfg["allowed_utc_hours"]):
        return

    # Persist this closed-bar watermark even when the prediction is HOLD. A
    # failed prediction rolls back the transaction and can retry next cycle.
    trader.last_decision_time = _naive_utc(decision_ts)
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
        adapter = resolve_event_execution_adapter(base_config.get("execution_mode", "paper"))
        if not adapter.capabilities.get("open"):
            logger.error(
                "[EventPaperTrader] trader %s (%s) selected live mode but no event-contract adapter is available",
                trader.id,
                trader.name,
            )
            return
        signal_id = (result.get("event_signal") or {}).get("signal_id")
        if signal_id and stored_config.get("last_signal_id") == signal_id:
            logger.info(
                "[EventPaperTrader] trader %s (%s) skipped duplicate signal_id=%s",
                trader.id,
                trader.name,
                signal_id,
            )
            return
        adapter.open(
            symbol=trader.symbol,
            direction=best_action,
            stake=trader.trade_margin or trader.stake_amount,
        )
        snapshot = {
            key: value
            for key, value in result.items()
            if key not in ("similar_patterns", "data_quality")
        }
        if signal_id:
            stored_config["last_signal_id"] = signal_id
            trader.config = json.dumps(stored_config, default=str)
        bet = EventContractPaperBet(
            trader_id=trader.id,
            direction=best_action,
            status="pending_entry",
            decision_time=_naive_utc(decision_ts),
            stake=trader.trade_margin or trader.stake_amount,
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
