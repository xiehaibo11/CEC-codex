"""Signal trigger log endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from schemas.signal import (
    SignalTriggerLogResponse,
    SignalTriggerLogsResponse,
)

from ._base import get_db, router


# ============ Trigger Logs ============

@router.get("/logs", response_model=SignalTriggerLogsResponse)
def get_trigger_logs(
    pool_id: Optional[int] = Query(None),
    signal_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get signal trigger logs with optional filters and pagination"""
    conditions = []
    params = {"limit": limit, "offset": offset}

    if pool_id is not None:
        conditions.append("pool_id = :pool_id")
        params["pool_id"] = pool_id
    if signal_id is not None:
        conditions.append("signal_id = :signal_id")
        params["signal_id"] = signal_id
    if symbol is not None:
        conditions.append("symbol = :symbol")
        params["symbol"] = symbol

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, signal_id, pool_id, symbol, trigger_value, triggered_at, market_regime
        FROM signal_trigger_logs {where_clause}
        ORDER BY triggered_at DESC LIMIT :limit OFFSET :offset
    """
    import json
    result = db.execute(text(query), params)
    logs = []
    for row in result:
        # Parse trigger_value - ORM defines as Text, so it may be string
        trigger_val = row[4]
        if isinstance(trigger_val, str):
            try:
                trigger_val = json.loads(trigger_val)
            except json.JSONDecodeError:
                trigger_val = None
        # Parse market_regime - also stored as Text/JSON
        market_regime_val = row[6]
        if isinstance(market_regime_val, str):
            try:
                market_regime_val = json.loads(market_regime_val)
            except json.JSONDecodeError:
                market_regime_val = None
        logs.append(SignalTriggerLogResponse(
            id=row[0], signal_id=row[1], pool_id=row[2],
            symbol=row[3], trigger_value=trigger_val, triggered_at=row[5],
            market_regime=market_regime_val
        ))

    # Get total count
    count_query = f"SELECT COUNT(*) FROM signal_trigger_logs {where_clause}"
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total = db.execute(text(count_query), count_params).scalar()

    return SignalTriggerLogsResponse(logs=logs, total=total)
