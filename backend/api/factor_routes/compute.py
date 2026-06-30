"""
Factor computation routes plus the background compute worker/state.

GET  /api/factors/compute/estimate  → Symbol list, coverage, estimated duration
POST /api/factors/compute           → Manual trigger (async background thread)
GET  /api/factors/compute/progress  → Computation progress
"""

import threading
from typing import List, Optional

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.connection import SessionLocal
from database.models import CustomFactor
from services.factor_timeframes import (
    FORWARD_PERIOD_SECONDS,
    get_forward_period_offsets,
    get_supported_factor_periods,
)

from .base import router, get_db

# Track background compute task
_compute_lock = threading.Lock()
_compute_result: Optional[dict] = None
_compute_running = False


class ComputeRequest(BaseModel):
    exchange: str = "hyperliquid"
    period: str = "1h"
    periods: Optional[List[str]] = None
    all_periods: bool = False


def _normalize_compute_periods(
    exchange: str,
    period: str = "1h",
    periods: Optional[List[str]] = None,
    all_periods: bool = False,
) -> List[str]:
    supported = get_supported_factor_periods(exchange)
    if all_periods:
        return supported

    raw_periods = periods or [period]
    normalized: List[str] = []
    for p in raw_periods:
        if p in supported and p not in normalized:
            normalized.append(p)
    return normalized or ["1h"]


def _run_compute_background(exchange: str, periods: List[str]):
    """Run factor computation in a background thread."""
    global _compute_result, _compute_running
    from services.factor_computation_service import factor_computation_service
    from services.factor_effectiveness_service import factor_effectiveness_service

    try:
        values_computed = 0
        effectiveness_computed = 0
        per_period = []
        for period in periods:
            val_result = factor_computation_service.compute_now(exchange, period)
            db = SessionLocal()
            try:
                eff_result = factor_effectiveness_service.compute_for_exchange(
                    db, exchange, period, force=True)
            finally:
                db.close()
            period_result = {
                "period": period,
                "values_computed": val_result.get("computed", 0),
                "effectiveness_computed": eff_result.get("computed", 0),
            }
            per_period.append(period_result)
            values_computed += period_result["values_computed"]
            effectiveness_computed += period_result["effectiveness_computed"]

        _compute_result = {
            "status": "done",
            "exchange": exchange,
            "period": periods[0] if len(periods) == 1 else "all",
            "kline_periods": periods,
            "values_computed": values_computed,
            "effectiveness_computed": effectiveness_computed,
            "per_period": per_period,
        }
    except Exception as e:
        _compute_result = {"status": "error", "error": str(e)}
    finally:
        _compute_running = False


@router.get("/compute/estimate")
async def compute_estimate(
    exchange: str = Query("hyperliquid"),
    period: str = Query("1h"),
    periods: Optional[str] = Query(None),
    all_periods: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Return symbol list, data coverage, and estimated duration."""
    from services.factor_computation_service import factor_computation_service
    from services.factor_registry import FACTOR_REGISTRY

    requested_periods = [p.strip() for p in periods.split(",")] if periods else None
    kline_periods = _normalize_compute_periods(
        exchange, period=period, periods=requested_periods, all_periods=all_periods,
    )
    symbols = factor_computation_service.get_symbols(exchange)
    # Count both builtin registry + active custom/builtin_expression factors
    custom_count = db.query(CustomFactor).filter(CustomFactor.is_active == True).count()
    factor_count = len(FACTOR_REGISTRY) + custom_count

    # Query actual data coverage per symbol
    coverage_by_period = {}
    if symbols:
        for kline_period in kline_periods:
            rows = db.execute(text("""
                SELECT symbol, COUNT(*) as cnt
                FROM crypto_klines
                WHERE exchange = :ex AND period = :period AND symbol = ANY(:syms)
                GROUP BY symbol
            """), {"ex": exchange, "period": kline_period, "syms": symbols}).fetchall()
            coverage_by_period[kline_period] = {r[0]: r[1] for r in rows}

    total_bars = sum(sum(period_cov.values()) for period_cov in coverage_by_period.values())
    divisor = len(symbols) * len(kline_periods) if symbols and kline_periods else 0
    avg_bars = total_bars // divisor if divisor else 0
    # Estimate: ~2s indicator computation + ~0.7s per factor per symbol (sliding window IC)
    # Benchmark: 2 symbols × 89 factors = 134s actual → ~0.75s per factor-symbol pair
    estimated_seconds = len(symbols) * len(kline_periods) * (2 + factor_count * 0.7)

    return {
        "exchange": exchange,
        "period": kline_periods[0] if len(kline_periods) == 1 else "all",
        "kline_period": kline_periods[0] if len(kline_periods) == 1 else "all",
        "kline_periods": kline_periods,
        "symbols": symbols,
        "symbol_count": len(symbols),
        "factor_count": factor_count,
        "forward_periods": list(FORWARD_PERIOD_SECONDS.keys()),
        "forward_periods_by_kline": {
            kline_period: list(get_forward_period_offsets(kline_period).keys())
            for kline_period in kline_periods
        },
        "coverage_by_period": coverage_by_period,
        "avg_bars_per_symbol": avg_bars,
        "total_bars": total_bars,
        "estimated_seconds": int(estimated_seconds),
    }


@router.post("/compute")
async def trigger_compute(req: ComputeRequest):
    """Start factor computation in background thread. Returns immediately."""
    global _compute_result, _compute_running
    periods = _normalize_compute_periods(
        req.exchange, period=req.period, periods=req.periods, all_periods=req.all_periods,
    )

    with _compute_lock:
        if _compute_running:
            return {"status": "already_running"}
        _compute_running = True
        _compute_result = None

    t = threading.Thread(
        target=_run_compute_background,
        args=(req.exchange, periods),
        daemon=True,
    )
    t.start()
    return {
        "status": "started",
        "exchange": req.exchange,
        "period": periods[0] if len(periods) == 1 else "all",
        "kline_periods": periods,
    }


@router.get("/compute/progress")
async def compute_progress():
    """Return current computation progress."""
    from services.factor_computation_service import factor_computation_service
    from services.factor_effectiveness_service import factor_effectiveness_service

    if not _compute_running:
        return _compute_result or {"status": "idle"}

    val_prog = factor_computation_service.get_progress()
    eff_prog = factor_effectiveness_service.get_progress()

    if eff_prog.get("status") == "running":
        return {
            "status": "running",
            "phase": "effectiveness",
            "period": eff_prog.get("period", ""),
            "current_symbol": eff_prog.get("current_symbol", ""),
            "completed": eff_prog.get("symbol_completed", 0),
            "total": eff_prog.get("symbol_total", 0),
            "current_factor": eff_prog.get("current_factor", ""),
            "factor_completed": eff_prog.get("factor_completed", 0),
            "factor_total": eff_prog.get("factor_total", 0),
        }
    if val_prog.get("status") == "running":
        return {
            "status": "running",
            "phase": "values",
            "period": val_prog.get("period", ""),
            "current_symbol": val_prog.get("current_symbol", ""),
            "completed": val_prog.get("completed", 0),
            "total": val_prog.get("total", 0),
        }
    return {"status": "running", "phase": "starting"}
