"""Signal pool CRUD endpoints."""
from __future__ import annotations

import json

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from schemas.signal import (
    SignalPoolCreate,
    SignalPoolUpdate,
    SignalPoolResponse,
)

from ._base import (
    MARKET_SIGNAL_SOURCE,
    WALLET_TRACKING_SOURCE,
    _build_pool_response,
    _normalize_source_config,
    _normalize_source_type,
    _schedule_wallet_tracking_refresh,
    get_db,
    router,
)


# ============ Signal Pools ============

@router.post("/pools", response_model=SignalPoolResponse)
def create_pool(payload: SignalPoolCreate, db: Session = Depends(get_db)):
    """Create a new signal pool"""
    source_type = _normalize_source_type(payload.source_type)
    source_config = _normalize_source_config(source_type, payload.source_config)

    # Validate that all signals belong to the same exchange as the pool
    if source_type == MARKET_SIGNAL_SOURCE and payload.signal_ids:
        result = db.execute(text("""
            SELECT id, exchange FROM signal_definitions WHERE id = ANY(:ids) AND (is_deleted IS NULL OR is_deleted = false)
        """), {"ids": payload.signal_ids})
        for row in result.fetchall():
            signal_exchange = row[1] or "hyperliquid"
            if signal_exchange != payload.exchange:
                raise HTTPException(
                    status_code=400,
                    detail=f"Signal {row[0]} belongs to {signal_exchange}, but pool is for {payload.exchange}"
                )

    result = db.execute(text("""
        INSERT INTO signal_pools (pool_name, signal_ids, symbols, enabled, logic, exchange, source_type, source_config)
        VALUES (:name, :signal_ids, :symbols, :enabled, :logic, :exchange, :source_type, :source_config)
        RETURNING id, pool_name, signal_ids, symbols, enabled, created_at, logic, exchange, source_type, source_config
    """), {
        "name": payload.pool_name,
        "signal_ids": json.dumps(payload.signal_ids if source_type == MARKET_SIGNAL_SOURCE else []),
        "symbols": json.dumps(payload.symbols if source_type == MARKET_SIGNAL_SOURCE else []),
        "enabled": payload.enabled,
        "logic": payload.logic,
        "exchange": payload.exchange,
        "source_type": source_type,
        "source_config": json.dumps(source_config),
    })
    db.commit()
    row = result.fetchone()
    response = _build_pool_response(row)
    _schedule_wallet_tracking_refresh()
    return response


@router.get("/pools/{pool_id}", response_model=SignalPoolResponse)
def get_pool(pool_id: int, db: Session = Depends(get_db)):
    """Get a signal pool by ID"""
    result = db.execute(text("""
        SELECT id, pool_name, signal_ids, symbols, enabled, created_at, logic, exchange, source_type, source_config
        FROM signal_pools WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
    """), {"id": pool_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Pool not found")
    return _build_pool_response(row)


@router.put("/pools/{pool_id}", response_model=SignalPoolResponse)
def update_pool(pool_id: int, payload: SignalPoolUpdate, db: Session = Depends(get_db)):
    """Update a signal pool"""
    current = db.execute(text("""
        SELECT exchange, source_type, source_config
        FROM signal_pools WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
    """), {"id": pool_id}).fetchone()
    if not current:
        raise HTTPException(status_code=404, detail="Pool not found")

    target_exchange = payload.exchange if payload.exchange is not None else (current[0] or "hyperliquid")
    target_source_type = _normalize_source_type(payload.source_type if payload.source_type is not None else current[1])
    target_source_config = _normalize_source_config(
        target_source_type,
        payload.source_config if payload.source_config is not None else current[2],
    )

    # Validate that all signals belong to the same exchange as the pool
    signal_ids_to_check = payload.signal_ids
    if target_source_type == MARKET_SIGNAL_SOURCE and signal_ids_to_check and target_exchange:
        result = db.execute(text("""
            SELECT id, exchange FROM signal_definitions WHERE id = ANY(:ids) AND (is_deleted IS NULL OR is_deleted = false)
        """), {"ids": signal_ids_to_check})
        for row in result.fetchall():
            signal_exchange = row[1] or "hyperliquid"
            if signal_exchange != target_exchange:
                raise HTTPException(
                    status_code=400,
                    detail=f"Signal {row[0]} belongs to {signal_exchange}, but pool is for {target_exchange}"
                )

    updates = []
    params = {"id": pool_id}
    if payload.pool_name is not None:
        updates.append("pool_name = :name")
        params["name"] = payload.pool_name
    if payload.signal_ids is not None:
        updates.append("signal_ids = :signal_ids")
        params["signal_ids"] = json.dumps(payload.signal_ids if target_source_type == MARKET_SIGNAL_SOURCE else [])
    if payload.symbols is not None:
        updates.append("symbols = :symbols")
        params["symbols"] = json.dumps(payload.symbols if target_source_type == MARKET_SIGNAL_SOURCE else [])
    if payload.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = payload.enabled
    if payload.logic is not None:
        updates.append("logic = :logic")
        params["logic"] = payload.logic
    if payload.exchange is not None:
        updates.append("exchange = :exchange")
        params["exchange"] = payload.exchange
    if payload.source_type is not None:
        updates.append("source_type = :source_type")
        params["source_type"] = target_source_type
        if target_source_type == WALLET_TRACKING_SOURCE:
            if payload.signal_ids is None:
                updates.append("signal_ids = '[]'")
            if payload.symbols is None:
                updates.append("symbols = '[]'")
    if payload.source_config is not None or payload.source_type is not None:
        updates.append("source_config = :source_config")
        params["source_config"] = json.dumps(target_source_config)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    query = f"""UPDATE signal_pools SET {', '.join(updates)}
        WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
        RETURNING id, pool_name, signal_ids, symbols, enabled, created_at, logic, exchange, source_type, source_config"""
    result = db.execute(text(query), params)
    db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Pool not found")
    response = _build_pool_response(row)
    _schedule_wallet_tracking_refresh()
    return response


@router.delete("/pools/{pool_id}")
def delete_pool(pool_id: int, db: Session = Depends(get_db)):
    """Soft-delete a signal pool with dependency checking."""
    from services.entity_deletion_service import delete_signal_pool
    result = delete_signal_pool(db, pool_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Pool not found"))
    _schedule_wallet_tracking_refresh()
    return result
