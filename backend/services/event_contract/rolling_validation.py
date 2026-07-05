"""Rolling out-of-sample validation cycle for event-contract strategies
(spec module 4).

Every 12h this appends a frozen-parameter holdout backtest run for every
strategy fingerprint that has an enabled paper trader, covering the window
since the last validation checkpoint (or since that fingerprint's most
recent backtest run, if no checkpoint exists yet). This automates what used
to require manually calling ``POST /backtest/{run_id}/holdout`` - the same
config-replay approach (load the stored config for the fingerprint's latest
backtest run, override the window, drop the window-derived
``reviewer_weights``) is reused here instead of duplicated.

``cumulative_validation_stats`` aggregates every ``status='recorded'`` window
for a fingerprint into a single Wilson-CI / binomial-significance readout, so
the frontend can show cumulative progress toward the target sample size
without the user re-running anything by hand.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models.event_contract import EventContractPaperTrader
from services.event_contract.backtest_stats import binomial_p_value, wilson_interval
from services.event_contract.paper_trader_api import _break_even_win_rate
from services.event_contract.tasks import (
    create_event_backtest_task,
    get_event_backtest_task,
    start_event_backtest_task_thread,
)

logger = logging.getLogger(__name__)

ROLLING_VALIDATION_JOB_ID = "event_rolling_validation_cycle"

# A new holdout window is only launched once this much wall-clock time has
# passed since the fingerprint's last validated window end.
WINDOW_SECONDS = 12 * 3600
# The new window's end trails "now" by this much, mirroring the live paper
# trader's caution around not asking for bars that haven't settled yet.
END_LAG_SECONDS = 15 * 60
# Sample size the frontend progress bar targets (spec module 4).
TARGET_N = 550

_SOURCE_RUN_LOOKUP_LIMIT = 500


def _rollback_safely(session: Session) -> None:
    """Roll back without letting rollback itself raise (mirrors
    ``live_paper_trader._rollback_safely`` - a failed statement on Postgres
    poisons the shared session for every subsequent fingerprint otherwise)."""
    try:
        session.rollback()
    except Exception:
        logger.exception("[RollingValidation] session.rollback() itself failed")


def run_rolling_validation_cycle(now_ts: Optional[int] = None, db: Optional[Session] = None) -> Dict[str, int]:
    """One cycle: record any completed/failed pending holdout tasks, then
    launch new holdout windows for fingerprints that are due.

    Injectable ``now_ts``/``db`` for tests. ``db`` defaults to a fresh
    ``SessionLocal`` that is closed before returning. Each fingerprint (both
    phases) commits or rolls back independently so one bad config/task never
    stalls the rest of the fleet.
    """
    resolved_now = int(now_ts) if now_ts is not None else int(datetime.now(timezone.utc).timestamp())
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        recorded = _record_phase(session)
        launched = _launch_phase(session, resolved_now)
    finally:
        if owns_session:
            session.close()
    return {"launched": launched, "recorded": recorded}


# ---------------------------------------------------------------------------
# RECORD phase
# ---------------------------------------------------------------------------


def _record_phase(session: Session) -> int:
    recorded = 0
    rows = session.execute(
        text(
            """
            SELECT id, task_id FROM event_contract_validation_log
            WHERE status = 'pending' AND task_id IS NOT NULL
            ORDER BY id ASC
            """
        )
    ).mappings().all()
    for row in rows:
        log_id = int(row["id"])
        task_id = int(row["task_id"])
        try:
            outcome = _record_one(session, log_id, task_id)
            session.commit()
            if outcome == "recorded":
                recorded += 1
        except Exception:
            _rollback_safely(session)
            logger.exception("[RollingValidation] record phase failed for validation_log %s", log_id)
    return recorded


def _record_one(session: Session, log_id: int, task_id: int) -> Optional[str]:
    try:
        task = get_event_backtest_task(session, task_id)
    except ValueError:
        # The task row is gone (e.g. pruned) - stop retrying it forever.
        _set_log_status(session, log_id, "failed")
        return "failed"

    status = task.get("status")
    if status == "completed" and task.get("run_id"):
        summary = _load_run_summary(session, int(task["run_id"]))
        wins = int(summary.get("wins") or 0)
        losses = int(summary.get("losses") or 0)
        session.execute(
            text(
                """
                UPDATE event_contract_validation_log
                SET status = 'recorded', decided = :decided, wins = :wins,
                    holdout_run_id = :run_id, updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {
                "decided": wins + losses,
                "wins": wins,
                "run_id": int(task["run_id"]),
                "id": log_id,
            },
        )
        return "recorded"
    if status == "failed":
        _set_log_status(session, log_id, "failed")
        return "failed"
    # still pending/running - leave untouched, next cycle re-checks it.
    return None


def _set_log_status(session: Session, log_id: int, status: str) -> None:
    session.execute(
        text(
            "UPDATE event_contract_validation_log SET status = :status, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = :id"
        ),
        {"status": status, "id": log_id},
    )


def _load_run_summary(session: Session, run_id: int) -> Dict[str, Any]:
    row = session.execute(
        text("SELECT summary FROM event_contract_backtest_runs WHERE id = :id"),
        {"id": run_id},
    ).first()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except (TypeError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# LAUNCH phase
# ---------------------------------------------------------------------------


def _launch_phase(session: Session, now_ts: int) -> int:
    launched = 0
    fingerprints = sorted(
        {
            fingerprint
            for (fingerprint,) in session.query(EventContractPaperTrader.strategy_fingerprint)
            .filter(EventContractPaperTrader.enabled.is_(True))
            .filter(EventContractPaperTrader.strategy_fingerprint.isnot(None))
            .distinct()
            .all()
            if fingerprint
        }
    )
    for fingerprint in fingerprints:
        try:
            if _launch_one(session, fingerprint, now_ts):
                launched += 1
            session.commit()
        except Exception:
            _rollback_safely(session)
            logger.exception("[RollingValidation] launch phase failed for fingerprint %s", fingerprint)
    return launched


def _launch_one(session: Session, fingerprint: str, now_ts: int) -> bool:
    source_run = _find_latest_source_run(session, fingerprint)
    if source_run is None:
        # No completed backtest run for this fingerprint yet - nothing to
        # replay with frozen parameters.
        return False

    # Guard against duplicate-launch: if a prior validation task is still
    # pending (long-running), skip launching another for this fingerprint.
    pending_row = session.execute(
        text(
            """
            SELECT id FROM event_contract_validation_log
            WHERE strategy_fingerprint = :fingerprint AND status = 'pending'
            LIMIT 1
            """
        ),
        {"fingerprint": fingerprint},
    ).first()
    if pending_row is not None:
        logger.debug(
            "[RollingValidation] skipping launch for fingerprint %s: "
            "prior validation task still pending",
            fingerprint,
        )
        return False

    last_end_ts = _latest_validation_window_end(session, fingerprint)
    if last_end_ts is None:
        last_end_ts = _epoch(source_run["end_time"])
    if last_end_ts is None:
        return False

    if now_ts - last_end_ts < WINDOW_SECONDS:
        return False

    window_end_ts = now_ts - END_LAG_SECONDS
    if window_end_ts <= last_end_ts:
        return False

    try:
        config = dict(json.loads(source_run["config"] or "{}"))
    except (TypeError, ValueError):
        config = {}
    config["start_time"] = _iso(last_end_ts)
    config["end_time"] = _iso(window_end_ts)
    config.pop("reviewer_weights", None)

    task = create_event_backtest_task(session, config=config, user_id=None)
    start_event_backtest_task_thread(task["task_id"])

    session.execute(
        text(
            """
            INSERT INTO event_contract_validation_log (
                strategy_fingerprint, source_run_id, task_id,
                window_start, window_end, status, created_at, updated_at
            ) VALUES (
                :fingerprint, :source_run_id, :task_id,
                :window_start, :window_end, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "fingerprint": fingerprint,
            "source_run_id": source_run["id"],
            "task_id": task["task_id"],
            "window_start": _naive_utc(last_end_ts),
            "window_end": _naive_utc(window_end_ts),
        },
    )
    return True


def _find_latest_source_run(session: Session, fingerprint: str) -> Optional[Dict[str, Any]]:
    """The most recent backtest run whose stored summary carries this
    fingerprint - same source the holdout endpoint replays a config from.

    Queries by fingerprint directly (Postgres jsonb) so an old source run is
    still found after hundreds of newer unrelated runs; the bounded recency
    scan remains as a fallback for non-jsonb backends / corrupt summary rows.
    """
    try:
        row = session.execute(
            text(
                """
                SELECT id, config, end_time
                FROM event_contract_backtest_runs
                WHERE status IN ('completed', 'partial')
                  AND summary::jsonb->>'strategy_fingerprint' = :fingerprint
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"fingerprint": fingerprint},
        ).mappings().first()
        if row is not None:
            return {"id": row["id"], "config": row["config"], "end_time": row["end_time"]}
        return None
    except Exception:
        _rollback_safely(session)
    rows = session.execute(
        text(
            """
            SELECT id, config, summary, end_time
            FROM event_contract_backtest_runs
            WHERE status IN ('completed', 'partial')
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {"limit": _SOURCE_RUN_LOOKUP_LIMIT},
    ).mappings().all()
    for row in rows:
        try:
            summary = json.loads(row["summary"] or "{}")
        except (TypeError, ValueError):
            continue
        if summary.get("strategy_fingerprint") == fingerprint:
            return {"id": row["id"], "config": row["config"], "end_time": row["end_time"]}
    return None


def _latest_validation_window_end(session: Session, fingerprint: str) -> Optional[int]:
    row = session.execute(
        text(
            """
            SELECT window_end FROM event_contract_validation_log
            WHERE strategy_fingerprint = :fingerprint AND window_end IS NOT NULL
            ORDER BY window_end DESC, id DESC
            LIMIT 1
            """
        ),
        {"fingerprint": fingerprint},
    ).first()
    if not row or row[0] is None:
        return None
    return _epoch(row[0])


# ---------------------------------------------------------------------------
# Cumulative stats
# ---------------------------------------------------------------------------


def cumulative_validation_stats(db: Session, fingerprint: str) -> Dict[str, Any]:
    """Aggregate every ``status='recorded'`` validation window for
    ``fingerprint`` into one cumulative Wilson-CI / significance readout,
    plus the full per-segment history for the frontend progress view."""
    rows = db.execute(
        text(
            """
            SELECT window_start, window_end, decided, wins, status, holdout_run_id
            FROM event_contract_validation_log
            WHERE strategy_fingerprint = :fingerprint
            ORDER BY window_start ASC, id ASC
            """
        ),
        {"fingerprint": fingerprint},
    ).mappings().all()

    segments = []
    total_decided = 0
    total_wins = 0
    for row in rows:
        decided = int(row["decided"] or 0)
        wins = int(row["wins"] or 0)
        segments.append(
            {
                "window_start": _iso_or_none(row["window_start"]),
                "window_end": _iso_or_none(row["window_end"]),
                "decided": decided,
                "wins": wins,
                "status": row["status"],
                "holdout_run_id": row["holdout_run_id"],
            }
        )
        if row["status"] == "recorded":
            total_decided += decided
            total_wins += wins

    break_even_win_rate = _break_even_for_fingerprint(db, fingerprint)
    decided_win_rate = round(total_wins / total_decided * 100, 2) if total_decided else 0.0
    ci_low, ci_high = wilson_interval(total_wins, total_decided)
    p_value = (
        binomial_p_value(total_wins, total_decided, break_even_win_rate / 100) if total_decided else 1.0
    )

    return {
        "fingerprint": fingerprint,
        "segments": segments,
        "n": total_decided,
        "wins": total_wins,
        "decided_win_rate": decided_win_rate,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "p_value": round(p_value, 6),
        "break_even_win_rate": round(break_even_win_rate, 2),
        "target_n": TARGET_N,
    }


def _break_even_for_fingerprint(db: Session, fingerprint: str) -> float:
    source_run = _find_latest_source_run(db, fingerprint)
    if source_run is None:
        return _break_even_win_rate({})
    try:
        config = json.loads(source_run["config"] or "{}")
    except (TypeError, ValueError):
        config = {}
    return _break_even_win_rate(config)


# ---------------------------------------------------------------------------
# Small time helpers (mirror services.event_contract.tasks._parse_dt /
# services.event_contract.live_paper_trader._naive_utc)
# ---------------------------------------------------------------------------


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        raw = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _epoch(value: Any) -> Optional[int]:
    dt = _parse_dt(value)
    return int(dt.timestamp()) if dt else None


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def _iso_or_none(value: Any) -> Optional[str]:
    dt = _parse_dt(value)
    return dt.isoformat() if dt else None


def _naive_utc(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
