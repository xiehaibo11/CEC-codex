"""Tier-1 "price-locked delayed-settlement arbitrage" OPPORTUNITY DETECTOR (MVP).

Full strategy: when spot has already locked in an event-contract outcome
(price beyond the strike, sustained for more than a third of the contract
period) but the venue still quotes the winning side below ~0.95, buy the
winning side. The stack has NO venue quote API for event contracts yet, so
this module is the DETECTOR + persistent opportunity log only: it measures how
often and how decisively "price-locked" moments occur on real market data,
producing the frequency/quality evidence that justifies (or kills) the venue
quote integration.

TODO(venue-quotes): once an event-contract quote API exists, join each locked
window against the venue's live quote for the locked side and record the
implied edge. Do NOT fake or simulate venue quotes in the meantime.

Mechanics (mirroring the platform's rolling 5-minute event contracts):
- Every minute starts a new hypothetical window: strike = that minute's open
  price, expiry 5 minutes later, so up to 5 windows overlap at any time.
- At evaluation time t a window is "locked" when BOTH hold, evaluated on 1m
  closes plus the latest live price (the forming bar's close):
    * price has been continuously on ONE side of the strike for
      >= max(100s, 1/3 of the window period), and
    * current |price - strike| / strike >= the minimum distance (default 0.05%).
- The first time a window locks, one row is written to arb_opportunity_log
  (unique per symbol+window). At expiry the row is settled in place against
  the expiry bar's open: outcome = win when the locked side actually won.

Runs on a 30-second scheduler tick via ``run_detector_cycle`` (injectable
``now_ts``/``db`` for tests, per-cycle DB session, per-symbol error isolation
- same style as services/event_contract/live_paper_trader.py).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models.arb import ArbOpportunityLog
from services.event_contract_service import event_contract_service

logger = logging.getLogger(__name__)

ARB_OPPORTUNITY_JOB_ID = "arb_opportunity_cycle"

_PERIOD = "1m"
_INTERVAL = 60

# Defaults; each is overridable via the environment variable named alongside.
DEFAULT_SYMBOLS = "BTC"                   # ARB_DETECTOR_SYMBOLS (comma-separated)
DEFAULT_EXCHANGE = "binance"              # ARB_DETECTOR_EXCHANGE
DEFAULT_ENVIRONMENT = "mainnet"           # ARB_DETECTOR_ENVIRONMENT
DEFAULT_WINDOW_MINUTES = 5                # ARB_DETECTOR_WINDOW_MINUTES
DEFAULT_MIN_SUSTAINED_FLOOR_SECONDS = 100  # ARB_MIN_SUSTAINED_SECONDS
DEFAULT_MIN_DISTANCE_PCT = 0.05           # ARB_MIN_DISTANCE_PCT (percent units)

# Settlement mirrors the paper trader's expiry tolerance: the expiry bar is the
# bar opening exactly at expiry, else the first bar within this many seconds
# after it. Past the tolerance with no bar, the row simply stays pending until
# a bar shows up (kline backfill) - never settled against a wrong price.
SETTLE_MAX_LAG_SECONDS = 120

# How far back to pull 1m bars when there are no pending rows to anchor on,
# and the hard cap for anchoring on very old pending rows.
_DEFAULT_LOOKBACK_SECONDS = 3600
_MAX_PENDING_LOOKBACK_SECONDS = 86400


def detector_settings() -> Dict[str, Any]:
    """Resolve detector configuration (env-overridable, safe defaults)."""
    window_minutes = int(os.getenv("ARB_DETECTOR_WINDOW_MINUTES", DEFAULT_WINDOW_MINUTES))
    window_seconds = max(window_minutes, 1) * 60
    sustained_floor = int(
        os.getenv("ARB_MIN_SUSTAINED_SECONDS", DEFAULT_MIN_SUSTAINED_FLOOR_SECONDS)
    )
    symbols = [
        item.strip().upper()
        for item in os.getenv("ARB_DETECTOR_SYMBOLS", DEFAULT_SYMBOLS).split(",")
        if item.strip()
    ]
    return {
        "symbols": symbols,
        "exchange": os.getenv("ARB_DETECTOR_EXCHANGE", DEFAULT_EXCHANGE),
        "environment": os.getenv("ARB_DETECTOR_ENVIRONMENT", DEFAULT_ENVIRONMENT),
        "window_seconds": window_seconds,
        # Both requirements from the strategy doc: >= max(100s, 1/3 period).
        "min_sustained_seconds": max(sustained_floor, window_seconds // 3),
        "min_distance_pct": float(os.getenv("ARB_MIN_DISTANCE_PCT", DEFAULT_MIN_DISTANCE_PCT)),
    }


def run_detector_cycle(now_ts: Optional[int] = None, db: Optional[Session] = None) -> Dict[str, int]:
    """One settle-then-detect pass over all configured symbols.

    Injectable ``now_ts``/``db`` for tests; ``db`` defaults to a fresh
    ``SessionLocal`` closed before returning. Each symbol commits (or rolls
    back) independently so one bad symbol never stalls the rest.
    """
    resolved_now = int(now_ts) if now_ts is not None else int(datetime.now(timezone.utc).timestamp())
    counters = {"locked": 0, "settled": 0, "errors": 0}
    settings = detector_settings()

    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        for symbol in settings["symbols"]:
            try:
                settled, locked = _run_symbol_cycle(session, symbol, settings, resolved_now)
                session.commit()
                counters["settled"] += settled
                counters["locked"] += locked
            except Exception:
                _rollback_safely(session)
                counters["errors"] += 1
                logger.exception("[ArbDetector] cycle failed for symbol %s", symbol)
    finally:
        if owns_session:
            session.close()
    return counters


def _rollback_safely(session: Session) -> None:
    """Roll back without letting rollback itself raise (aborted-txn guard)."""
    try:
        session.rollback()
    except Exception:
        logger.exception("[ArbDetector] session.rollback() itself failed")


def _run_symbol_cycle(
    session: Session, symbol: str, settings: Dict[str, Any], now_ts: int
) -> Tuple[int, int]:
    pending_rows = (
        session.query(ArbOpportunityLog)
        .filter(ArbOpportunityLog.symbol == symbol, ArbOpportunityLog.outcome == "pending")
        .all()
    )
    klines = _load_symbol_klines(session, symbol, settings, pending_rows, now_ts)
    ts_to_bar = {int(item["timestamp"]): item for item in klines}

    settled = _settle_due_rows(pending_rows, klines, ts_to_bar, settings, now_ts)
    locked = _detect_locks(session, symbol, klines, ts_to_bar, settings, now_ts)
    return settled, locked


def _load_symbol_klines(
    session: Session,
    symbol: str,
    settings: Dict[str, Any],
    pending_rows: List[ArbOpportunityLog],
    now_ts: int,
) -> List[Dict[str, Any]]:
    candidates = [now_ts - _DEFAULT_LOOKBACK_SECONDS]
    for row in pending_rows:
        expiry_ts = _epoch(row.window_start) + settings["window_seconds"]
        candidates.append(max(expiry_ts, now_ts - _MAX_PENDING_LOOKBACK_SECONDS))
    start_ts = min(candidates) - _INTERVAL
    return event_contract_service._load_klines(
        session, settings["exchange"], symbol, _PERIOD, start_ts, now_ts, settings["environment"]
    )


def _settle_due_rows(
    pending_rows: List[ArbOpportunityLog],
    klines: List[Dict[str, Any]],
    ts_to_bar: Dict[int, Dict[str, Any]],
    settings: Dict[str, Any],
    now_ts: int,
) -> int:
    settled = 0
    for row in pending_rows:
        expiry_ts = _epoch(row.window_start) + settings["window_seconds"]
        if expiry_ts > now_ts:
            continue
        expiry_bar = ts_to_bar.get(expiry_ts)
        if expiry_bar is None:
            # Tolerance fallback: first bar within SETTLE_MAX_LAG_SECONDS after
            # expiry (data gaps). Otherwise leave the row pending for a later
            # cycle - never settle against a price from the wrong moment.
            laggards = [
                item
                for item in klines
                if expiry_ts < int(item["timestamp"]) <= expiry_ts + SETTLE_MAX_LAG_SECONDS
            ]
            expiry_bar = min(laggards, key=lambda item: item["timestamp"]) if laggards else None
        if expiry_bar is None:
            continue

        final_price = float(expiry_bar["open"])
        strike = float(row.strike)
        if row.direction == "above":
            won = final_price > strike
        else:
            won = final_price < strike
        row.final_price = final_price
        row.outcome = "win" if won else "loss"
        settled += 1
    return settled


def _detect_locks(
    session: Session,
    symbol: str,
    klines: List[Dict[str, Any]],
    ts_to_bar: Dict[int, Dict[str, Any]],
    settings: Dict[str, Any],
    now_ts: int,
) -> int:
    window_seconds = settings["window_seconds"]
    latest_minute = (now_ts // _INTERVAL) * _INTERVAL
    active_starts = [
        latest_minute - offset * _INTERVAL
        for offset in range(window_seconds // _INTERVAL)
    ]
    active_starts = [start for start in active_starts if start <= now_ts < start + window_seconds]
    if not active_starts:
        return 0

    existing = {
        row[0]
        for row in session.query(ArbOpportunityLog.window_start)
        .filter(
            ArbOpportunityLog.symbol == symbol,
            ArbOpportunityLog.window_start.in_([_naive_utc(s) for s in active_starts]),
        )
        .all()
    }

    locked = 0
    for window_start in active_starts:
        if _naive_utc(window_start) in existing:
            continue
        strike_bar = ts_to_bar.get(window_start)
        if strike_bar is None:
            continue
        strike = float(strike_bar["open"])
        if strike <= 0:
            continue

        observations = _window_observations(klines, window_start, now_ts)
        verdict = evaluate_window(
            strike,
            observations,
            now_ts,
            settings["min_sustained_seconds"],
            settings["min_distance_pct"],
        )
        if verdict is None:
            continue

        session.add(
            ArbOpportunityLog(
                symbol=symbol,
                window_start=_naive_utc(window_start),
                strike=strike,
                direction=verdict["direction"],
                locked_at=_naive_utc(now_ts),
                remaining_seconds=window_start + window_seconds - now_ts,
                distance_pct=verdict["distance_pct"],
                outcome="pending",
            )
        )
        locked += 1
        logger.info(
            "[ArbDetector] %s window %s LOCKED %s: strike=%s distance=%.4f%% "
            "sustained=%ss remaining=%ss (no venue quote leg yet - detector only)",
            symbol, window_start, verdict["direction"], strike,
            verdict["distance_pct"], verdict["sustained_seconds"],
            window_start + window_seconds - now_ts,
        )
    return locked


def _window_observations(
    klines: List[Dict[str, Any]], window_start: int, now_ts: int
) -> List[Tuple[int, float]]:
    """(observation_time, price) points for a window: each 1m close observed at
    the bar's close time, the still-forming bar's close observed at ``now`` as
    the latest live price."""
    observations = [
        (min(int(item["timestamp"]) + _INTERVAL, now_ts), float(item["close"]))
        for item in klines
        if window_start <= int(item["timestamp"]) <= now_ts
    ]
    observations.sort(key=lambda pair: pair[0])
    return observations


def evaluate_window(
    strike: float,
    observations: List[Tuple[int, float]],
    now_ts: int,
    min_sustained_seconds: int,
    min_distance_pct: float,
) -> Optional[Dict[str, Any]]:
    """Pure lock check for one window. Returns None, or the lock verdict.

    Locked when the current one-sided streak (walked backwards over the
    observations; a touch of the strike breaks it) has been held for at least
    ``min_sustained_seconds`` AND the live distance clears ``min_distance_pct``.
    """
    if not observations:
        return None
    live_price = observations[-1][1]
    side = _side(live_price, strike)
    if side is None:
        return None

    streak_start: Optional[int] = None
    for obs_time, price in reversed(observations):
        if _side(price, strike) != side:
            break
        streak_start = obs_time
    if streak_start is None:
        return None

    sustained_seconds = now_ts - streak_start
    if sustained_seconds < min_sustained_seconds:
        return None

    distance_pct = abs(live_price - strike) / strike * 100.0
    if distance_pct < min_distance_pct:
        return None

    return {
        "direction": side,
        "distance_pct": distance_pct,
        "sustained_seconds": sustained_seconds,
    }


def _side(price: float, strike: float) -> Optional[str]:
    if price > strike:
        return "above"
    if price < strike:
        return "below"
    return None


def summarize_opportunities(db: Session) -> Dict[str, Any]:
    """KPI aggregates for GET /api/arb/summary: lock accuracy + count by day."""
    outcome_counts = dict(
        db.query(ArbOpportunityLog.outcome, func.count(ArbOpportunityLog.id))
        .group_by(ArbOpportunityLog.outcome)
        .all()
    )
    wins = int(outcome_counts.get("win", 0))
    losses = int(outcome_counts.get("loss", 0))
    pending = int(outcome_counts.get("pending", 0))
    decided = wins + losses

    day = func.date(ArbOpportunityLog.locked_at)
    daily_rows = (
        db.query(
            day.label("day"),
            func.count(ArbOpportunityLog.id),
            func.sum(_outcome_flag("win")),
            func.sum(_outcome_flag("loss")),
            func.sum(_outcome_flag("pending")),
        )
        .group_by(day)
        .order_by(day)
        .all()
    )
    daily = [
        {
            "date": str(row[0]),
            "count": int(row[1] or 0),
            "wins": int(row[2] or 0),
            "losses": int(row[3] or 0),
            "pending": int(row[4] or 0),
        }
        for row in daily_rows
    ]

    return {
        "total": wins + losses + pending,
        "pending": pending,
        "wins": wins,
        "losses": losses,
        "decided": decided,
        "lock_accuracy_pct": round(wins / decided * 100.0, 2) if decided else None,
        "daily": daily,
        # Honest-scope marker: these KPIs justify (or kill) building the venue
        # quote leg; no venue quotes exist in this data.
        "note": "detector-only MVP: no venue quotes involved",
    }


def serialize_opportunity(row: ArbOpportunityLog) -> Dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "window_start": row.window_start.isoformat() if row.window_start else None,
        "strike": row.strike,
        "direction": row.direction,
        "locked_at": row.locked_at.isoformat() if row.locked_at else None,
        "remaining_seconds": row.remaining_seconds,
        "distance_pct": row.distance_pct,
        "final_price": row.final_price,
        "outcome": row.outcome,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _outcome_flag(outcome: str):
    return case((ArbOpportunityLog.outcome == outcome, 1), else_=0)


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
