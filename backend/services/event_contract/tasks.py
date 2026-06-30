"""Task-state helpers for long-running event-contract backtests."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from services.event_contract.constants import EVENT_AI_NAMES

logger = logging.getLogger(__name__)

TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_PAUSE_REQUESTED = "pause_requested"
TASK_STATUS_PAUSED = "paused"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

DEFAULT_PROGRESS_WEIGHTS = {"data": 0.15, "bars": 0.65, "ai": 0.20}


class EventBacktestPaused(Exception):
    """Raised inside the backtest loop when the persisted task requests pause."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_progress(
    *,
    data_ready: bool,
    processed_decision_bars: int,
    total_decision_bars: int,
    completed_ai_reviews: int,
    expected_ai_reviews: int,
    weights: Optional[Mapping[str, float]] = None,
) -> float:
    raw_weights = dict(DEFAULT_PROGRESS_WEIGHTS if weights is None else weights)
    total_weight = sum(max(float(value), 0.0) for value in raw_weights.values()) or 1.0
    normalized = {key: max(float(value), 0.0) / total_weight for key, value in raw_weights.items()}
    bar_ratio = _ratio(processed_decision_bars, total_decision_bars)
    ai_ratio = _ratio(completed_ai_reviews, expected_ai_reviews)
    value = (
        normalized.get("data", 0.0) * (1.0 if data_ready else 0.0)
        + normalized.get("bars", 0.0) * bar_ratio
        + normalized.get("ai", 0.0) * ai_ratio
    ) * 100
    return round(max(0.0, min(100.0, value)), 2)


def _ratio(done: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, float(done) / float(total)))


def build_ai_reviewer_statuses(
    decisions: Iterable[Mapping[str, Any]] | None = None,
    *,
    status: str = "pending",
    active_name: str | None = None,
) -> List[Dict[str, Any]]:
    by_name = {str(item.get("ai_name", "")).strip(): dict(item) for item in decisions or []}
    result: List[Dict[str, Any]] = []
    for name in EVENT_AI_NAMES:
        item = by_name.get(name)
        if item:
            result.append(
                {
                    "ai_name": name,
                    "status": "completed",
                    "direction": item.get("direction"),
                    "confidence": item.get("confidence"),
                    "reason": item.get("reason"),
                    "model": item.get("model"),
                    "account_name": item.get("account_name"),
                    "error": None,
                }
            )
        else:
            result.append(
                {
                    "ai_name": name,
                    "status": "running" if active_name == name else status,
                    "direction": None,
                    "confidence": None,
                    "reason": "",
                    "model": None,
                    "account_name": None,
                    "error": None,
                }
            )
    return result


def create_event_backtest_task(
    db: Session,
    *,
    config: Dict[str, Any],
    user_id: int | None = None,
    name: str | None = None,
) -> Dict[str, Any]:
    public_config = {key: value for key, value in config.items() if not key.startswith("_")}
    # rule_only mode never calls the LLM reviewers, so seed each reviewer slot with
    # "skipped" instead of "pending" - keeps the UI honest about what's running.
    initial_reviewer_status = (
        "skipped" if str(public_config.get("consensus_mode") or "").lower() == "rule_only" else "pending"
    )
    result = db.execute(
        text(
            """
            INSERT INTO event_contract_backtest_tasks (
                user_id, name, status, symbol, exchange, environment, period,
                config, progress_pct, phase, ai_reviewer_statuses,
                created_at, updated_at
            ) VALUES (
                :user_id, :name, :status, :symbol, :exchange, :environment, :period,
                :config, 0, :phase, :ai_reviewer_statuses,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id
            """
        ),
        {
            "user_id": user_id,
            "name": name,
            "status": TASK_STATUS_PENDING,
            "symbol": str(public_config.get("symbol") or "BTC").upper(),
            "exchange": str(public_config.get("exchange") or "binance").lower(),
            "environment": str(public_config.get("environment") or "mainnet").lower(),
            "period": str(public_config.get("period") or "1m"),
            "config": json.dumps(public_config),
            "phase": "queued",
            "ai_reviewer_statuses": json.dumps(build_ai_reviewer_statuses(status=initial_reviewer_status)),
        },
    )
    task_id = int(result.scalar_one())
    db.commit()
    return get_event_backtest_task(db, task_id)


def get_event_backtest_task(db: Session, task_id: int) -> Dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT id, user_id, run_id, name, status, symbol, exchange, environment,
                   period, config, progress_pct, phase, processed_decision_bars,
                   total_decision_bars, completed_ai_reviews, expected_ai_reviews,
                   ai_reviewer_statuses, latest_message, error_message,
                   started_at, finished_at, created_at, updated_at
            FROM event_contract_backtest_tasks
            WHERE id = :task_id
            """
        ),
        {"task_id": task_id},
    ).mappings().first()
    if not row:
        raise ValueError(f"Event backtest task {task_id} not found")
    return _row_to_task(row)


def request_event_backtest_pause(db: Session, task_id: int) -> Dict[str, Any]:
    db.execute(
        text(
            """
            UPDATE event_contract_backtest_tasks
            SET status = CASE
                    WHEN status IN ('pending', 'running') THEN 'pause_requested'
                    ELSE status
                END,
                latest_message = CASE
                    WHEN status IN ('pending', 'running') THEN 'Pause requested'
                    ELSE latest_message
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :task_id
            """
        ),
        {"task_id": task_id},
    )
    db.commit()
    return get_event_backtest_task(db, task_id)


def is_event_backtest_pause_requested(db: Session, task_id: int) -> bool:
    status = db.execute(
        text("SELECT status FROM event_contract_backtest_tasks WHERE id = :task_id"),
        {"task_id": task_id},
    ).scalar()
    return status == TASK_STATUS_PAUSE_REQUESTED


def update_event_backtest_task(
    db: Session,
    task_id: int,
    *,
    status: str | None = None,
    phase: str | None = None,
    progress_pct: float | None = None,
    processed_decision_bars: int | None = None,
    total_decision_bars: int | None = None,
    completed_ai_reviews: int | None = None,
    expected_ai_reviews: int | None = None,
    ai_reviewer_statuses: List[Dict[str, Any]] | None = None,
    run_id: int | None = None,
    latest_message: str | None = None,
    error_message: str | None = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    assignments = ["updated_at = CURRENT_TIMESTAMP"]
    params: Dict[str, Any] = {"task_id": task_id}
    optional_values = {
        "status": status,
        "phase": phase,
        "progress_pct": progress_pct,
        "processed_decision_bars": processed_decision_bars,
        "total_decision_bars": total_decision_bars,
        "completed_ai_reviews": completed_ai_reviews,
        "expected_ai_reviews": expected_ai_reviews,
        "run_id": run_id,
        "latest_message": latest_message,
        "error_message": error_message,
    }
    for column, value in optional_values.items():
        if value is not None:
            assignments.append(f"{column} = :{column}")
            params[column] = value
    if ai_reviewer_statuses is not None:
        assignments.append("ai_reviewer_statuses = :ai_reviewer_statuses")
        params["ai_reviewer_statuses"] = json.dumps(ai_reviewer_statuses)
    if started:
        assignments.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
    if finished:
        assignments.append("finished_at = CURRENT_TIMESTAMP")
    db.execute(
        text(f"UPDATE event_contract_backtest_tasks SET {', '.join(assignments)} WHERE id = :task_id"),
        params,
    )
    db.commit()


def start_event_backtest_task_thread(task_id: int) -> None:
    thread = threading.Thread(target=run_event_backtest_task, args=(task_id,), daemon=True)
    thread.start()


def run_event_backtest_task(task_id: int) -> None:
    from database.models import CoinGlassUserKey
    from services.event_contract_service import event_contract_service
    from utils.encryption import decrypt_private_key

    db = SessionLocal()
    try:
        task = get_event_backtest_task(db, task_id)
        config = dict(task.get("config") or {})
        if config.get("enable_coinglass_features") and task.get("user_id"):
            record = db.query(CoinGlassUserKey).filter(CoinGlassUserKey.user_id == task["user_id"]).first()
            if record:
                config["_coinglass_api_key"] = decrypt_private_key(record.api_key_encrypted)
                config["_coinglass_key_source"] = "user"
        update_event_backtest_task(
            db,
            task_id,
            status=TASK_STATUS_RUNNING,
            phase="starting",
            latest_message="Backtest started",
            started=True,
        )

        def progress_callback(event: Dict[str, Any]) -> None:
            _apply_progress_event(db, task_id, event)

        def pause_checker() -> bool:
            return is_event_backtest_pause_requested(db, task_id)

        result = event_contract_service.run_backtest(
            db,
            config,
            progress_callback=progress_callback,
            pause_checker=pause_checker,
        )
        update_event_backtest_task(
            db,
            task_id,
            status=TASK_STATUS_COMPLETED,
            phase="completed",
            progress_pct=100,
            run_id=result.get("run_id"),
            latest_message="Backtest completed",
            finished=True,
        )
    except EventBacktestPaused:
        update_event_backtest_task(
            db,
            task_id,
            status=TASK_STATUS_PAUSED,
            phase="paused",
            latest_message="Paused by user",
            finished=True,
        )
    except Exception as exc:  # noqa: BLE001 - persisted task must capture failures
        logger.exception("Event backtest task %s failed", task_id)
        db.rollback()
        update_event_backtest_task(
            db,
            task_id,
            status=TASK_STATUS_FAILED,
            phase="failed",
            error_message=str(exc)[:1000],
            latest_message="Backtest failed",
            finished=True,
        )
    finally:
        db.close()


def _apply_progress_event(db: Session, task_id: int, event: Dict[str, Any]) -> None:
    task = get_event_backtest_task(db, task_id)
    processed = int(event.get("processed_decision_bars") or task.get("processed_decision_bars") or 0)
    total = int(event.get("total_decision_bars") or task.get("total_decision_bars") or 0)
    completed_ai = int(event.get("completed_ai_reviews") or task.get("completed_ai_reviews") or 0)
    expected_ai = int(event.get("expected_ai_reviews") or task.get("expected_ai_reviews") or 0)
    data_ready = bool(event.get("data_ready") or task.get("phase") not in ("queued", "starting", "loading_data"))
    progress_pct = event.get("progress_pct")
    if progress_pct is None:
        progress_pct = compute_progress(
            data_ready=data_ready,
            processed_decision_bars=processed,
            total_decision_bars=total,
            completed_ai_reviews=completed_ai,
            expected_ai_reviews=expected_ai,
            weights=event.get("progress_weights"),
        )
    update_event_backtest_task(
        db,
        task_id,
        status=TASK_STATUS_RUNNING,
        phase=event.get("phase"),
        progress_pct=float(progress_pct),
        processed_decision_bars=processed,
        total_decision_bars=total,
        completed_ai_reviews=completed_ai,
        expected_ai_reviews=expected_ai,
        ai_reviewer_statuses=event.get("ai_reviewer_statuses"),
        latest_message=event.get("message"),
    )


def _row_to_task(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": row["id"],
        "id": row["id"],
        "user_id": row.get("user_id"),
        "run_id": row.get("run_id"),
        "name": row.get("name"),
        "status": row.get("status"),
        "symbol": row.get("symbol"),
        "exchange": row.get("exchange"),
        "environment": row.get("environment"),
        "period": row.get("period"),
        "config": _json(row.get("config"), {}),
        "progress_pct": float(row.get("progress_pct") or 0),
        "phase": row.get("phase") or "",
        "processed_decision_bars": int(row.get("processed_decision_bars") or 0),
        "total_decision_bars": int(row.get("total_decision_bars") or 0),
        "completed_ai_reviews": int(row.get("completed_ai_reviews") or 0),
        "expected_ai_reviews": int(row.get("expected_ai_reviews") or 0),
        "ai_reviewer_statuses": _json(row.get("ai_reviewer_statuses"), []),
        "latest_message": row.get("latest_message"),
        "error_message": row.get("error_message"),
        "started_at": _dt_to_iso(row.get("started_at")),
        "finished_at": _dt_to_iso(row.get("finished_at")),
        "created_at": _dt_to_iso(row.get("created_at")),
        "updated_at": _dt_to_iso(row.get("updated_at")),
    }


def _json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _dt_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)
