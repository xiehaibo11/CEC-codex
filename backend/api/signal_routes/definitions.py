"""Signal definition endpoints (list + CRUD)."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from schemas.signal import (
    SignalDefinitionCreate,
    SignalDefinitionUpdate,
    SignalDefinitionResponse,
    SignalListResponse,
)

from ._base import _build_pool_response, _parse_json_text, get_db, router


# ============ Signal Definitions ============

@router.get("", response_model=SignalListResponse)
@router.get("/", response_model=SignalListResponse)
def list_signals(db: Session = Depends(get_db)) -> SignalListResponse:
    """List all signal definitions and pools"""
    signals_result = db.execute(text("""
        SELECT id, signal_name, description, trigger_condition, enabled, created_at, updated_at, exchange
        FROM signal_definitions WHERE (is_deleted IS NULL OR is_deleted = false) ORDER BY id
    """))
    signals = []
    for row in signals_result:
        # Parse trigger_condition from JSON string if needed
        trigger_condition = row[3]
        trigger_condition = _parse_json_text(trigger_condition, {})
        signals.append(SignalDefinitionResponse(
            id=row[0], signal_name=row[1], description=row[2],
            trigger_condition=trigger_condition, enabled=row[4],
            created_at=row[5], updated_at=row[6], exchange=row[7] or "hyperliquid"
        ))

    pools_result = db.execute(text("""
        SELECT id, pool_name, signal_ids, symbols, enabled, created_at, logic, exchange, source_type, source_config
        FROM signal_pools WHERE (is_deleted IS NULL OR is_deleted = false) ORDER BY id
    """))
    pools = []
    for row in pools_result:
        pools.append(_build_pool_response(row))

    return SignalListResponse(signals=signals, pools=pools)


@router.post("/definitions", response_model=SignalDefinitionResponse)
def create_signal(payload: SignalDefinitionCreate, db: Session = Depends(get_db)):
    """Create a new signal definition"""
    import json
    result = db.execute(text("""
        INSERT INTO signal_definitions (signal_name, description, trigger_condition, enabled, exchange)
        VALUES (:name, :desc, :condition, :enabled, :exchange)
        RETURNING id, signal_name, description, trigger_condition, enabled, created_at, updated_at, exchange
    """), {
        "name": payload.signal_name,
        "desc": payload.description,
        "condition": json.dumps(payload.trigger_condition),
        "enabled": payload.enabled,
        "exchange": payload.exchange
    })
    db.commit()
    row = result.fetchone()
    trigger_condition = row[3]
    if isinstance(trigger_condition, str):
        trigger_condition = json.loads(trigger_condition)
    return SignalDefinitionResponse(
        id=row[0], signal_name=row[1], description=row[2],
        trigger_condition=trigger_condition, enabled=row[4],
        created_at=row[5], updated_at=row[6], exchange=row[7] or "hyperliquid"
    )


@router.get("/definitions/{signal_id}", response_model=SignalDefinitionResponse)
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    """Get a signal definition by ID"""
    import json
    result = db.execute(text("""
        SELECT id, signal_name, description, trigger_condition, enabled, created_at, updated_at, exchange
        FROM signal_definitions WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
    """), {"id": signal_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    trigger_condition = row[3]
    if isinstance(trigger_condition, str):
        trigger_condition = json.loads(trigger_condition)
    return SignalDefinitionResponse(
        id=row[0], signal_name=row[1], description=row[2],
        trigger_condition=trigger_condition, enabled=row[4],
        created_at=row[5], updated_at=row[6], exchange=row[7] or "hyperliquid"
    )


@router.put("/definitions/{signal_id}", response_model=SignalDefinitionResponse)
def update_signal(signal_id: int, payload: SignalDefinitionUpdate, db: Session = Depends(get_db)):
    """Update a signal definition"""
    import json
    # Build dynamic update query
    updates = []
    params = {"id": signal_id}
    if payload.signal_name is not None:
        updates.append("signal_name = :name")
        params["name"] = payload.signal_name
    if payload.description is not None:
        updates.append("description = :desc")
        params["desc"] = payload.description
    if payload.trigger_condition is not None:
        updates.append("trigger_condition = :condition")
        params["condition"] = json.dumps(payload.trigger_condition)
    if payload.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = payload.enabled
    if payload.exchange is not None:
        updates.append("exchange = :exchange")
        params["exchange"] = payload.exchange

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE signal_definitions SET {', '.join(updates)} WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false) RETURNING id, signal_name, description, trigger_condition, enabled, created_at, updated_at, exchange"
    result = db.execute(text(query), params)
    db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    trigger_condition = row[3]
    if isinstance(trigger_condition, str):
        trigger_condition = json.loads(trigger_condition)
    return SignalDefinitionResponse(
        id=row[0], signal_name=row[1], description=row[2],
        trigger_condition=trigger_condition, enabled=row[4],
        created_at=row[5], updated_at=row[6], exchange=row[7] or "hyperliquid"
    )


@router.delete("/definitions/{signal_id}")
def delete_signal(signal_id: int, db: Session = Depends(get_db)):
    """Soft-delete a signal definition with dependency checking."""
    from services.entity_deletion_service import delete_signal_definition
    result = delete_signal_definition(db, signal_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Signal not found"))
    return result
