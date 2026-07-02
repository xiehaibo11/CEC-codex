"""API routes for the 5-minute event contract prediction/backtest tool."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth_dependencies import get_current_user
from database.connection import SessionLocal
from database.models import CoinGlassUserKey
from services.event_contract_service import event_contract_service
from services.event_contract.tasks import (
    create_event_backtest_task,
    find_latest_event_backtest_task,
    get_event_backtest_task,
    request_event_backtest_pause,
    start_event_backtest_task_thread,
)
from utils.encryption import decrypt_private_key


router = APIRouter(prefix="/api/event-contract", tags=["event-contract"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PredictRequest(BaseModel):
    symbol: str = "BTC"
    exchange: str = "binance"
    environment: str = "mainnet"
    period: str = "1m"
    expiry_minutes: int = 5
    consensus_mode: str = Field(default="rule_only", pattern="^(ai_confirmed|rule_only)$")
    decision_policy: str = Field(default="professional_v1", pattern="^(professional_v1|legacy_vote)$")
    ai_trader_id: Optional[int] = None
    max_ai_evaluations: int = Field(default=1, ge=1, le=200)
    consensus_threshold: int = Field(default=5, ge=1, le=31)
    reviewer_panel_size: int = Field(default=25, ge=5, le=31)
    target_win_rate: float = Field(default=75, ge=0, le=100)
    target_min_trades: int = Field(default=10, ge=1, le=10000)
    enable_edge_quality_gate: bool = True
    max_trade_range_risk: float = Field(default=45, ge=0, le=100)
    allow_pullback_trades: bool = False
    enable_fake_breakout_filter: bool = True
    enable_trap_filter: bool = True
    enable_range_filter: bool = True
    enable_multi_timeframe_filter: bool = True
    enable_volume_filter: bool = True
    enable_cvd_filter: bool = False
    enable_coinglass_features: bool = False
    min_coinglass_coverage_pct: Optional[float] = Field(default=96, ge=0, le=100)
    strict_coinglass_quality: bool = True
    coinglass_metrics: Optional[List[str]] = None
    coinglass_interval: Optional[str] = Field(default=None, description="CoinGlass sampling interval (e.g. '30m', '1h'). Default = K-line period. Standard plan needs >= 30m.")
    coinglass_no_future_leakage: bool = True
    max_entry_lag_seconds: Optional[int] = Field(default=None, ge=0, le=10800)
    max_expiry_lag_seconds: Optional[int] = Field(default=None, ge=0, le=10800)
    min_data_coverage_pct: Optional[float] = Field(default=None, ge=0, le=100)
    strict_data_quality: bool = False
    enable_l2_features: bool = False
    min_l2_coverage_pct: Optional[float] = Field(default=96, ge=0, le=100)
    strict_l2_quality: bool = True
    max_l2_lag_seconds: Optional[int] = Field(default=None, ge=0, le=10800)


class BacktestRequest(PredictRequest):
    start_time: str
    end_time: str
    initial_balance: float = Field(default=10000, gt=0)
    stake_amount: float = Field(default=100, gt=0)
    platform: str = Field(default="custom", pattern="^(hibt|binance_event|custom)$")
    win_payout_ratio: Optional[float] = Field(default=None, ge=0)
    fee_rate: Optional[float] = Field(default=None, ge=0)
    slippage_bps: float = Field(default=0, ge=0)
    delay_seconds: int = Field(default=3, ge=0)
    draw_result: Optional[str] = Field(default=None, pattern="^(loss|draw|refund)$")
    max_bars: int = Field(default=50000, ge=100, le=200000)
    max_ai_evaluations: int = Field(default=20, ge=1, le=200)
    non_overlapping_only: bool = True


@router.get("/symbols")
def get_symbols(exchange: Optional[str] = Query(None), db: Session = Depends(get_db)):
    try:
        return {
            "symbols": event_contract_service.get_available_symbols(db, exchange=exchange),
            "default_exchange": "binance",
            "default_symbol": "BTC",
            "supported_periods": ["1m", "3m", "5m", "15m", "30m", "1h"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/predict")
def predict_event_contract(request: Request, payload: PredictRequest, db: Session = Depends(get_db)):
    try:
        config = _attach_user_coinglass_key(payload.model_dump(), request, db)
        return event_contract_service.predict(db, config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")


@router.post("/backtest")
def backtest_event_contract(request: Request, payload_model: BacktestRequest, db: Session = Depends(get_db)):
    try:
        payload: Dict[str, Any] = _attach_user_coinglass_key(payload_model.model_dump(), request, db)
        return event_contract_service.run_backtest(db, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")


@router.post("/backtest/tasks")
def create_backtest_task(request: Request, payload_model: BacktestRequest, db: Session = Depends(get_db)):
    try:
        payload: Dict[str, Any] = payload_model.model_dump()
        task = create_event_backtest_task(
            db,
            config=payload,
            user_id=_current_user_id(request, db),
        )
        start_event_backtest_task_thread(task["task_id"])
        return task
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Backtest task failed to start: {exc}")


@router.get("/backtest/tasks/latest")
def get_latest_backtest_task(request: Request, db: Session = Depends(get_db)):
    try:
        task = find_latest_event_backtest_task(db, user_id=_current_user_id(request, db))
        if not task:
            return None
        if task.get("run_id"):
            task["result"] = event_contract_service.get_backtest_response(db, task["run_id"])
        return task
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/backtest/tasks/{task_id}")
def get_backtest_task(task_id: int, db: Session = Depends(get_db)):
    try:
        task = get_event_backtest_task(db, task_id)
        if task.get("run_id"):
            task["result"] = event_contract_service.get_backtest_response(db, task["run_id"])
        return task
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/backtest/tasks/{task_id}/pause")
def pause_backtest_task(task_id: int, db: Session = Depends(get_db)):
    try:
        return request_event_backtest_pause(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class HoldoutRequest(BaseModel):
    start_time: str
    end_time: str


@router.post("/backtest/{run_id}/holdout")
def create_holdout_task(run_id: int, payload: HoldoutRequest, request: Request, db: Session = Depends(get_db)):
    """Re-run a stored config on a fresh window (frozen-parameter OOS check)."""
    try:
        import json as _json
        from sqlalchemy import text as _text
        row = db.execute(
            _text("SELECT config, summary FROM event_contract_backtest_runs WHERE id = :id"),
            {"id": run_id},
        ).first()
        if not row:
            raise ValueError(f"Backtest run {run_id} not found")
        config = _json.loads(row[0] or "{}")
        config["start_time"] = payload.start_time
        config["end_time"] = payload.end_time
        config.pop("reviewer_weights", None)
        task = create_event_backtest_task(db, config=config, user_id=_current_user_id(request, db))
        start_event_backtest_task_thread(task["task_id"])
        summary = _json.loads(row[1] or "{}")
        task["source_run_id"] = run_id
        task["strategy_fingerprint"] = summary.get("strategy_fingerprint")
        return task
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Holdout task failed to start: {exc}")


def _attach_user_coinglass_key(payload: Dict[str, Any], request: Request, db: Session) -> Dict[str, Any]:
    if not payload.get("enable_coinglass_features"):
        return payload
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return payload
    record = db.query(CoinGlassUserKey).filter(CoinGlassUserKey.user_id == current_user.id).first()
    if not record:
        return payload
    payload["_coinglass_api_key"] = decrypt_private_key(record.api_key_encrypted)
    payload["_coinglass_key_source"] = "user"
    return payload


def _current_user_id(request: Request, db: Session) -> Optional[int]:
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return None
    return getattr(current_user, "id", None)


@router.get("/backtest/{run_id}")
def get_backtest_result(run_id: int, db: Session = Depends(get_db)):
    try:
        return event_contract_service.get_backtest_result(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/backtest/{run_id}/trades")
def get_backtest_trades(
    run_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return event_contract_service.get_trade_logs(db, run_id, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/reviewers/stats")
def get_reviewer_team_stats(db: Session = Depends(get_db)):
    """Bayesian learning snapshot for the 30-reviewer panel.

    Returns each reviewer's posterior accuracy, evolution score, current
    vote weight, and the risk_flags it has emitted most. Used by the
    Dashboard team-stats panel to show which reviewers have earned trust.
    """
    try:
        from services.event_contract.reviewer_learning import get_reviewer_evolution_snapshot
        from services.event_contract.reviewer_expertise import REVIEWER_EXPERTISE
        snapshot = get_reviewer_evolution_snapshot(db)
        return {
            "reviewers": snapshot,
            "expertise": {name: payload for name, payload in REVIEWER_EXPERTISE.items()},
            "lookback_trades": 1500,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
