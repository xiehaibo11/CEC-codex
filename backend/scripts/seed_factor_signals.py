"""Seed the factor-driven reversal signal pool (spec module 5).

Creates four ``factor:``-metric signal definitions off the strongest scored BTC
factors (``LOG_RETURN_1`` reversal, ``DEPTH_RATIO`` order-book imbalance),
groups them into an OR pool ``因子反转池``, and binds that pool onto account 3's
``account_strategy_configs.signal_pool_ids`` so the scheduled trigger loop
(``scheduled_trigger_enabled`` - left untouched) picks it up.

Thresholds are derived live from ``factor_values`` percentiles over the
trailing lookback window (default 30 days), using a linear-interpolation
percentile identical to PostgreSQL's ``percentile_cont``:
    - LOG_RETURN_1: P5 (oversold -> long-bias reversal) / P95 (overbought ->
      short-bias reversal)
    - DEPTH_RATIO:  P90 (bid-heavy imbalance) / P10 (ask-heavy imbalance)

trigger_condition uses the canonical schema read by
``signal_detection_service`` (``services/signal_detection_service/conditions.py``):
``{"metric": "factor:<NAME>", "operator": "<"|">", "threshold": <float>,
"time_window": "1h"}``. This is the same key ("metric", not "indicator") that
``api/signal_routes/pool_config.py`` already writes when persisting AI-built
pools - see that route's ``sig.get("metric") or sig.get("indicator")``
fallback, which this seed script's chosen key naturally satisfies.

Idempotent: if a signal/pool with the target name already exists (and is not
soft-deleted), it is reused as-is (no update, no duplicate). Binding is
idempotent too: the pool id is only appended to account 3's
``signal_pool_ids`` if not already present; no other column on that row is
touched.

Usage:
    uv run python scripts/seed_factor_signals.py [--symbol BTC] [--exchange binance]
        [--account-id 3] [--lookback-days 30] [--time-window 1h]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database.connection import SessionLocal  # noqa: E402
from database.models.signals import SignalDefinition, SignalPool  # noqa: E402
from database.models.trading import AccountStrategyConfig  # noqa: E402

DEFAULT_SYMBOL = "BTC"
DEFAULT_EXCHANGE = "binance"
DEFAULT_ACCOUNT_ID = 3
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_TIME_WINDOW = "1h"
MIN_SAMPLES = 10  # below this, percentiles are too noisy to seed a threshold from

POOL_NAME = "因子反转池"


# ============ Pure helpers (no DB access - unit-testable with fake data) ============

def percentile_cont(values: Sequence[float], pct: float) -> float:
    """Linear-interpolation percentile, matching PostgreSQL's percentile_cont(pct).

    Given a non-empty sequence of values and a target fraction in [0, 1],
    returns the interpolated value at that percentile. This mirrors the exact
    algorithm PostgreSQL uses for ``percentile_cont`` so results computed here
    from raw rows match what an equivalent SQL query would return.
    """
    if not values:
        raise ValueError("values must be non-empty")
    if not 0.0 <= pct <= 1.0:
        raise ValueError("pct must be within [0, 1]")

    xs = sorted(values)
    n = len(xs)
    if n == 1:
        return xs[0]

    rank = pct * (n - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return xs[lower]
    frac = rank - lower
    return xs[lower] + frac * (xs[upper] - xs[lower])


def derive_log_return_thresholds(values: Sequence[float]) -> Tuple[float, float]:
    """P5/P95 thresholds for LOG_RETURN_1 reversal signals, rounded to 6dp
    (LOG_RETURN_1 values are small fractional returns, e.g. ~0.005)."""
    p5 = round(percentile_cont(values, 0.05), 6)
    p95 = round(percentile_cont(values, 0.95), 6)
    return p5, p95


def derive_depth_ratio_thresholds(values: Sequence[float]) -> Tuple[float, float]:
    """P10/P90 thresholds for DEPTH_RATIO imbalance signals, rounded to 3dp
    (DEPTH_RATIO is a bid/ask depth ratio, typically single digits)."""
    p10 = round(percentile_cont(values, 0.10), 3)
    p90 = round(percentile_cont(values, 0.90), 3)
    return p10, p90


def build_signal_specs(
    log_return_p5: float,
    log_return_p95: float,
    depth_ratio_p10: float,
    depth_ratio_p90: float,
    time_window: str = DEFAULT_TIME_WINDOW,
) -> List[Dict[str, Any]]:
    """Build the 4 factor signal specs (name, description, trigger_condition)."""
    return [
        {
            "signal_name": "LOG_RETURN_1 超跌反转",
            "description": (
                f"LOG_RETURN_1 低于近 {{lookback_days}} 日 P5 阈值 {log_return_p5}"
                "，视为超跌，反转做多信号背景"
            ),
            "trigger_condition": {
                "metric": "factor:LOG_RETURN_1",
                "operator": "<",
                "threshold": log_return_p5,
                "time_window": time_window,
            },
        },
        {
            "signal_name": "LOG_RETURN_1 超涨反转",
            "description": (
                f"LOG_RETURN_1 高于近 {{lookback_days}} 日 P95 阈值 {log_return_p95}"
                "，视为超涨，反转做空信号背景"
            ),
            "trigger_condition": {
                "metric": "factor:LOG_RETURN_1",
                "operator": ">",
                "threshold": log_return_p95,
                "time_window": time_window,
            },
        },
        {
            "signal_name": "DEPTH_RATIO 买盘失衡",
            "description": (
                f"DEPTH_RATIO 高于近 {{lookback_days}} 日 P90 阈值 {depth_ratio_p90}"
                "，买盘深度显著占优"
            ),
            "trigger_condition": {
                "metric": "factor:DEPTH_RATIO",
                "operator": ">",
                "threshold": depth_ratio_p90,
                "time_window": time_window,
            },
        },
        {
            "signal_name": "DEPTH_RATIO 卖盘失衡",
            "description": (
                f"DEPTH_RATIO 低于近 {{lookback_days}} 日 P10 阈值 {depth_ratio_p10}"
                "，卖盘深度显著占优"
            ),
            "trigger_condition": {
                "metric": "factor:DEPTH_RATIO",
                "operator": "<",
                "threshold": depth_ratio_p10,
                "time_window": time_window,
            },
        },
    ]


# ============ DB-backed helpers ============

def fetch_factor_values(
    db: Session,
    factor_name: str,
    symbol: str,
    exchange: str,
    lookback_days: int,
    period: str = DEFAULT_TIME_WINDOW,
) -> List[float]:
    """Fetch raw factor_values.value samples for the trailing lookback window."""
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp())
    rows = db.execute(
        text(
            """
            SELECT value FROM factor_values
            WHERE factor_name = :factor_name AND symbol = :symbol AND exchange = :exchange
              AND period = :period AND timestamp >= :cutoff_ts AND value IS NOT NULL
            ORDER BY timestamp
            """
        ),
        {
            "factor_name": factor_name,
            "symbol": symbol,
            "exchange": exchange,
            "period": period,
            "cutoff_ts": cutoff_ts,
        },
    ).fetchall()
    return [float(r[0]) for r in rows]


def _not_deleted(model):
    return or_(model.is_deleted.is_(False), model.is_deleted.is_(None))


def get_or_create_signal(
    db: Session,
    signal_name: str,
    description: Optional[str],
    trigger_condition: Dict[str, Any],
    exchange: str,
) -> Tuple[int, bool]:
    """Idempotent signal lookup/create by name. Returns (id, created)."""
    existing = (
        db.query(SignalDefinition)
        .filter(SignalDefinition.signal_name == signal_name)
        .filter(_not_deleted(SignalDefinition))
        .first()
    )
    if existing is not None:
        return existing.id, False

    row = SignalDefinition(
        signal_name=signal_name,
        description=description,
        trigger_condition=json.dumps(trigger_condition, ensure_ascii=False),
        enabled=True,
        exchange=exchange,
    )
    db.add(row)
    db.flush()
    return row.id, True


def get_or_create_pool(
    db: Session,
    pool_name: str,
    signal_ids: List[int],
    symbols: List[str],
    logic: str,
    exchange: str,
) -> Tuple[int, bool]:
    """Idempotent pool lookup/create by name. Returns (id, created)."""
    existing = (
        db.query(SignalPool)
        .filter(SignalPool.pool_name == pool_name)
        .filter(_not_deleted(SignalPool))
        .first()
    )
    if existing is not None:
        return existing.id, False

    row = SignalPool(
        pool_name=pool_name,
        signal_ids=json.dumps(signal_ids),
        symbols=json.dumps(symbols),
        logic=logic,
        enabled=True,
        exchange=exchange,
        source_type="market_signals",
        source_config="{}",
    )
    db.add(row)
    db.flush()
    return row.id, True


def bind_pool_to_account(db: Session, account_id: int, pool_id: int) -> bool:
    """Append pool_id to account_strategy_configs.signal_pool_ids for account_id,
    preserving every other column (notably scheduled_trigger_enabled). Idempotent:
    returns False (no-op) if the pool id is already present."""
    cfg = (
        db.query(AccountStrategyConfig)
        .filter(AccountStrategyConfig.account_id == account_id)
        .first()
    )
    if cfg is None:
        raise SystemExit(
            f"account_strategy_configs row not found for account_id={account_id}"
        )

    existing_ids: List[int] = json.loads(cfg.signal_pool_ids) if cfg.signal_pool_ids else []
    if pool_id in existing_ids:
        return False

    existing_ids.append(pool_id)
    cfg.signal_pool_ids = json.dumps(existing_ids)
    db.flush()
    return True


# ============ Orchestration ============

def seed(
    db: Session,
    symbol: str = DEFAULT_SYMBOL,
    exchange: str = DEFAULT_EXCHANGE,
    account_id: int = DEFAULT_ACCOUNT_ID,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    time_window: str = DEFAULT_TIME_WINDOW,
) -> Dict[str, Any]:
    """Run the full seed flow against an open session and return a summary dict.
    Does not commit - caller controls the transaction boundary."""
    log_return_values = fetch_factor_values(
        db, "LOG_RETURN_1", symbol, exchange, lookback_days, time_window
    )
    depth_ratio_values = fetch_factor_values(
        db, "DEPTH_RATIO", symbol, exchange, lookback_days, time_window
    )

    if len(log_return_values) < MIN_SAMPLES:
        raise SystemExit(
            f"Only {len(log_return_values)} LOG_RETURN_1 samples in the trailing "
            f"{lookback_days}d for {symbol}/{exchange} - need >= {MIN_SAMPLES} to "
            "derive stable percentile thresholds."
        )
    if len(depth_ratio_values) < MIN_SAMPLES:
        raise SystemExit(
            f"Only {len(depth_ratio_values)} DEPTH_RATIO samples in the trailing "
            f"{lookback_days}d for {symbol}/{exchange} - need >= {MIN_SAMPLES} to "
            "derive stable percentile thresholds."
        )

    log_return_p5, log_return_p95 = derive_log_return_thresholds(log_return_values)
    depth_ratio_p10, depth_ratio_p90 = derive_depth_ratio_thresholds(depth_ratio_values)

    specs = build_signal_specs(
        log_return_p5, log_return_p95, depth_ratio_p10, depth_ratio_p90, time_window
    )
    for spec in specs:
        spec["description"] = spec["description"].format(lookback_days=lookback_days)

    signal_results = []
    signal_ids = []
    for spec in specs:
        sid, created = get_or_create_signal(
            db, spec["signal_name"], spec["description"], spec["trigger_condition"], exchange
        )
        signal_ids.append(sid)
        signal_results.append(
            {
                "id": sid,
                "signal_name": spec["signal_name"],
                "created": created,
                "trigger_condition": spec["trigger_condition"],
            }
        )

    pool_id, pool_created = get_or_create_pool(
        db, POOL_NAME, signal_ids, [symbol], "OR", exchange
    )

    bound = bind_pool_to_account(db, account_id, pool_id)

    return {
        "symbol": symbol,
        "exchange": exchange,
        "lookback_days": lookback_days,
        "time_window": time_window,
        "thresholds": {
            "LOG_RETURN_1": {"p5": log_return_p5, "p95": log_return_p95,
                              "samples": len(log_return_values)},
            "DEPTH_RATIO": {"p10": depth_ratio_p10, "p90": depth_ratio_p90,
                             "samples": len(depth_ratio_values)},
        },
        "signals": signal_results,
        "pool": {"id": pool_id, "pool_name": POOL_NAME, "created": pool_created},
        "account_id": account_id,
        "bound": bound,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--exchange", default=DEFAULT_EXCHANGE)
    parser.add_argument("--account-id", type=int, default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--time-window", default=DEFAULT_TIME_WINDOW)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = seed(
            db,
            symbol=args.symbol,
            exchange=args.exchange,
            account_id=args.account_id,
            lookback_days=args.lookback_days,
            time_window=args.time_window,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
