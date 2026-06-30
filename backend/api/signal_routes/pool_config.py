"""AI signal pool creation from generated configuration."""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from ._base import MARKET_SIGNAL_SOURCE, get_db, router


# ============ AI Signal Pool Creation ============

class SignalPoolConfigRequest(BaseModel):
    """Request for creating signal pool from AI-generated config"""
    name: str = Field(..., description="Pool name")
    symbol: str = Field(..., description="Trading symbol (e.g., BTC)")
    description: Optional[str] = Field(None, description="Pool description")
    logic: str = Field("AND", description="Combination logic: AND or OR")
    signals: List[dict] = Field(..., description="List of signal configurations")
    exchange: str = Field("hyperliquid", description="Exchange: hyperliquid or binance")

    class Config:
        populate_by_name = True


@router.post("/create-pool-from-config")
def create_pool_from_config(
    request: SignalPoolConfigRequest,
    db: Session = Depends(get_db)
):
    """
    Create a signal pool from AI-generated configuration.
    Creates individual signals and combines them into a pool.
    """
    import json

    if not request.signals:
        raise HTTPException(status_code=400, detail="No signals provided")

    if len(request.signals) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 signals per pool")

    created_signal_ids = []
    created_signals = []

    try:
        # Create each signal
        for i, sig in enumerate(request.signals):
            # Generate signal name if not provided
            sig_name = sig.get("name") or f"{request.name}_{i+1}"

            # Build trigger condition - handle taker_volume composite signal specially
            metric_name = sig.get("metric") or sig.get("indicator")

            if metric_name == "taker_volume":
                # taker_volume uses direction/ratio_threshold/volume_threshold instead of operator/threshold
                trigger_condition = {
                    "metric": metric_name,
                    "direction": sig.get("direction"),
                    "ratio_threshold": sig.get("ratio_threshold"),
                    "volume_threshold": sig.get("volume_threshold"),
                    "time_window": sig.get("time_window")
                }
                # Validate taker_volume required fields
                if not all([trigger_condition["metric"], trigger_condition["direction"],
                           trigger_condition["ratio_threshold"] is not None,
                           trigger_condition["volume_threshold"] is not None,
                           trigger_condition["time_window"]]):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Signal {i+1} (taker_volume) missing required fields (direction, ratio_threshold, volume_threshold, time_window)"
                    )
            else:
                # Standard signal with operator/threshold
                trigger_condition = {
                    "metric": metric_name,
                    "operator": sig.get("operator"),
                    "threshold": sig.get("threshold"),
                    "time_window": sig.get("time_window")
                }
                # Validate standard signal required fields
                if not all([trigger_condition["metric"], trigger_condition["operator"],
                           trigger_condition["threshold"] is not None, trigger_condition["time_window"]]):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Signal {i+1} missing required fields (metric, operator, threshold, time_window)"
                    )

            # Create signal with exchange
            result = db.execute(text("""
                INSERT INTO signal_definitions (signal_name, description, trigger_condition, enabled, exchange)
                VALUES (:name, :desc, :condition, :enabled, :exchange)
                RETURNING id, signal_name, description, trigger_condition, enabled, created_at, exchange
            """), {
                "name": sig_name,
                "desc": sig.get("description") or f"Part of {request.name}",
                "condition": json.dumps(trigger_condition),
                "enabled": True,
                "exchange": request.exchange
            })
            row = result.fetchone()
            created_signal_ids.append(row[0])
            created_signals.append({
                "id": row[0],
                "signal_name": row[1],
                "trigger_condition": trigger_condition,
                "exchange": request.exchange
            })

        # Create the pool with exchange
        pool_result = db.execute(text("""
            INSERT INTO signal_pools (pool_name, signal_ids, symbols, enabled, logic, exchange, source_type, source_config)
            VALUES (:name, :signal_ids, :symbols, :enabled, :logic, :exchange, :source_type, :source_config)
            RETURNING id, pool_name, signal_ids, symbols, enabled, created_at, logic, exchange, source_type, source_config
        """), {
            "name": request.name,
            "signal_ids": json.dumps(created_signal_ids),
            "symbols": json.dumps([request.symbol]),
            "enabled": True,
            "logic": request.logic,
            "exchange": request.exchange,
            "source_type": MARKET_SIGNAL_SOURCE,
            "source_config": json.dumps({}),
        })
        pool_row = pool_result.fetchone()

        db.commit()

        return {
            "success": True,
            "pool": {
                "id": pool_row[0],
                "pool_name": pool_row[1],
                "signal_ids": created_signal_ids,
                "symbols": [request.symbol],
                "logic": request.logic,
                "exchange": request.exchange,
                "source_type": MARKET_SIGNAL_SOURCE,
                "source_config": {},
            },
            "signals": created_signals
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create pool: {str(e)}")
