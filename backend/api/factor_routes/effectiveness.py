"""
Factor effectiveness / scoring routes plus engine status.

GET /api/factors/effectiveness                          → Effectiveness ranking
GET /api/factors/effectiveness/{name}/history           → IC trend over time
GET /api/factors/effectiveness/{name}/by-window         → Latest IC per forward period
GET /api/factors/status                                 → Engine status
"""

from datetime import date, timedelta

from fastapi import Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.factor_registry import FACTOR_REGISTRY

from .base import router, get_db


@router.get("/effectiveness")
async def get_factor_effectiveness(
    symbol: str = Query(...),
    period: str = Query("1h"),
    forward_period: str = Query("4h"),
    exchange: str = Query("hyperliquid"),
    sort_by: str = Query("icir"),
    db: Session = Depends(get_db),
):
    """Return effectiveness ranking for a symbol/period/forward_period."""
    valid_sorts = {"icir", "ic_mean", "win_rate", "sample_count"}
    col = sort_by if sort_by in valid_sorts else "icir"

    rows = db.execute(text(f"""
        SELECT DISTINCT ON (factor_name)
            factor_name, factor_category, ic_mean, ic_std, icir,
            win_rate, decay_half_life, sample_count, calc_date
        FROM factor_effectiveness
        WHERE symbol = :sym AND period = :p AND forward_period = :fp AND exchange = :ex
        ORDER BY factor_name, calc_date DESC
    """), {"sym": symbol, "p": period, "fp": forward_period, "ex": exchange}).fetchall()

    # Compute IC 7-day average for trend comparison
    cutoff_7d = date.today() - timedelta(days=7)
    ic_7d_rows = db.execute(text("""
        SELECT factor_name, AVG(ic_mean) as ic_7d
        FROM factor_effectiveness
        WHERE symbol = :sym AND period = :p AND forward_period = :fp
            AND exchange = :ex AND calc_date >= :cutoff
        GROUP BY factor_name
    """), {"sym": symbol, "p": period, "fp": forward_period,
           "ex": exchange, "cutoff": cutoff_7d}).fetchall()
    ic_7d_map = {r[0]: round(float(r[1]), 6) if r[1] is not None else None for r in ic_7d_rows}

    items = []
    for r in rows:
        fname = r[0]
        ic_30d = r[2]  # ic_mean from latest calc (uses full history)
        ic_7d = ic_7d_map.get(fname)
        # Trend: compare recent 7d IC direction with long-term IC direction
        ic_trend = None
        if ic_7d is not None and ic_30d is not None and abs(ic_30d) > 1e-6:
            ic_trend = round(ic_7d / ic_30d, 2)
        items.append({
            "factor_name": fname, "category": r[1],
            "ic_mean": ic_30d, "ic_std": r[3], "icir": r[4],
            "win_rate": r[5], "decay_half_life": r[6],
            "sample_count": r[7], "calc_date": str(r[8]),
            "ic_7d": ic_7d, "ic_trend": ic_trend,
        })
    items.sort(key=lambda x: abs(x.get(col) or 0), reverse=True)

    return {
        "symbol": symbol, "period": period,
        "forward_period": forward_period, "exchange": exchange,
        "items": items,
    }


@router.get("/effectiveness/{factor_name}/history")
async def get_effectiveness_history(
    factor_name: str,
    symbol: str = Query(...),
    period: str = Query("1h"),
    forward_period: str = Query("4h"),
    exchange: str = Query("hyperliquid"),
    days: int = Query(30),
    db: Session = Depends(get_db),
):
    """Return IC trend over time for a specific factor."""
    cutoff = date.today() - timedelta(days=days)
    rows = db.execute(text("""
        SELECT calc_date, ic_mean, icir, win_rate, sample_count
        FROM factor_effectiveness
        WHERE exchange = :ex AND factor_name = :fn AND symbol = :sym AND period = :p
            AND forward_period = :fp AND calc_date >= :cutoff
        ORDER BY calc_date
    """), {"ex": exchange, "fn": factor_name, "sym": symbol, "p": period,
           "fp": forward_period, "cutoff": cutoff}).fetchall()

    return {
        "factor_name": factor_name,
        "history": [
            {"date": str(r[0]), "ic_mean": r[1], "icir": r[2],
             "win_rate": r[3], "sample_count": r[4]}
            for r in rows
        ],
    }


@router.get("/effectiveness/{factor_name}/by-window")
async def get_effectiveness_by_window(
    factor_name: str,
    symbol: str = Query(...),
    period: str = Query("1h"),
    exchange: str = Query("hyperliquid"),
    db: Session = Depends(get_db),
):
    """Return latest IC across all forward periods for bar chart visualization."""
    rows = db.execute(text("""
        SELECT DISTINCT ON (forward_period)
            forward_period, ic_mean, icir, win_rate, sample_count
        FROM factor_effectiveness
        WHERE factor_name = :fn AND symbol = :sym AND period = :p AND exchange = :ex
        ORDER BY forward_period, calc_date DESC
    """), {"fn": factor_name, "sym": symbol, "p": period, "ex": exchange}).fetchall()

    return {
        "factor_name": factor_name,
        "windows": [
            {"forward_period": r[0], "ic_mean": r[1], "icir": r[2],
             "win_rate": r[3], "sample_count": r[4]}
            for r in rows
        ],
    }


@router.get("/status")
async def get_factor_status(db: Session = Depends(get_db)):
    """Return engine status with per-exchange last compute time."""
    import os
    enabled = os.getenv("FACTOR_ENGINE_ENABLED", "false").lower() == "true"

    from services.factor_computation_service import factor_computation_service

    stats = db.execute(text("""
        SELECT COUNT(*), COUNT(DISTINCT symbol), MAX(timestamp), MAX(created_at)
        FROM factor_values
    """)).fetchone()

    eff_stats = db.execute(text("""
        SELECT COUNT(*), MAX(calc_date) FROM factor_effectiveness
    """)).fetchone()

    # Use DB created_at as persistent last compute time, fallback to in-memory
    db_last_compute = None
    if stats and stats[3]:
        db_last_compute = stats[3].timestamp() if hasattr(stats[3], 'timestamp') else None

    mem_hl = factor_computation_service.get_last_compute_time("hyperliquid")
    mem_bn = factor_computation_service.get_last_compute_time("binance")

    return {
        "enabled": enabled,
        "total_factor_values": stats[0] if stats else 0,
        "symbols_covered": stats[1] if stats else 0,
        "latest_computation_ts": stats[2] if stats else None,
        "total_effectiveness_records": eff_stats[0] if eff_stats else 0,
        "latest_effectiveness_date": str(eff_stats[1]) if eff_stats and eff_stats[1] else None,
        "registered_factors": len(FACTOR_REGISTRY),
        "last_compute_time": {
            "hyperliquid": mem_hl or db_last_compute,
            "binance": mem_bn or db_last_compute,
        },
        "compute_interval_seconds": 3600,
    }
