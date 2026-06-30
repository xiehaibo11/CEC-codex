"""Signal testing and monitoring endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from ._base import get_db, router


# ============ Signal Testing & Monitoring ============

@router.get("/test/{signal_id}")
def test_signal(
    signal_id: int,
    symbol: str = Query(..., description="Symbol to test against"),
    db: Session = Depends(get_db)
):
    """
    Test a signal against current market data.
    Returns the current metric value and whether the condition is met.
    """
    import json
    from services.signal_detection_service import signal_detection_service
    from services.market_flow_collector import market_flow_collector

    # Get signal definition
    result = db.execute(text("""
        SELECT id, signal_name, description, trigger_condition, enabled
        FROM signal_definitions WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
    """), {"id": signal_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Parse trigger_condition - may be string (TEXT) or dict (JSONB)
    trigger_condition = row[3]
    if isinstance(trigger_condition, str):
        try:
            trigger_condition = json.loads(trigger_condition)
        except json.JSONDecodeError:
            trigger_condition = {}

    signal_def = {
        "id": row[0],
        "signal_name": row[1],
        "description": row[2],
        "trigger_condition": trigger_condition,
        "enabled": row[4]
    }

    # Get current market data from collector
    market_data = {
        "asset_ctx": market_flow_collector.latest_asset_ctx.get(symbol, {}),
        "orderbook": market_flow_collector.latest_orderbook.get(symbol, {}),
    }

    condition = signal_def.get("trigger_condition", {})
    metric = condition.get("metric")
    operator = condition.get("operator")
    threshold = condition.get("threshold")
    time_window = condition.get("time_window", 60)

    # Get current metric value
    current_value = signal_detection_service._get_metric_value(
        metric, symbol, market_data, time_window
    )

    # Evaluate condition
    condition_met = False
    if current_value is not None:
        condition_met = signal_detection_service._evaluate_condition(
            current_value, operator, threshold
        )

    # Get signal state
    state_key = (signal_id, symbol)
    state = signal_detection_service.signal_states.get(state_key)

    return {
        "signal_id": signal_id,
        "signal_name": signal_def["signal_name"],
        "symbol": symbol,
        "metric": metric,
        "operator": operator,
        "threshold": threshold,
        "time_window": time_window,
        "current_value": current_value,
        "condition_met": condition_met,
        "is_active": state.is_active if state else False,
        "would_trigger": condition_met and (not state or not state.is_active),
        "market_data_available": bool(market_data.get("asset_ctx")),
    }


@router.get("/states")
def get_signal_states():
    """Get current signal states for monitoring"""
    from services.signal_detection_service import signal_detection_service
    return {
        "states": signal_detection_service.get_signal_states(),
        "cache_info": {
            "pools_count": len(signal_detection_service._signal_pools_cache),
            "signals_count": len(signal_detection_service._signals_cache),
        }
    }


@router.post("/states/reset")
def reset_signal_states(
    signal_id: Optional[int] = Query(None),
    pool_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None)
):
    """Reset signal and pool states (useful for testing)"""
    from services.signal_detection_service import signal_detection_service
    signal_detection_service.reset_state(signal_id, pool_id, symbol)
    return {"message": "Signal and pool states reset successfully"}
