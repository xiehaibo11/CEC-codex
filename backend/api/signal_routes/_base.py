"""Shared core for signal system API routes.

Defines the shared APIRouter instance, module-level constants, the DB session
dependency, and JSON/source-config helpers used across the endpoint modules.
"""
from __future__ import annotations

import logging
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.connection import SessionLocal
from schemas.signal import SignalPoolResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/signals", tags=["Signal System"])

MARKET_SIGNAL_SOURCE = "market_signals"
WALLET_TRACKING_SOURCE = "wallet_tracking"
COINGLASS_WALLET_TRACKING_ENDPOINTS = (
    ("whale_position", "/api/hyperliquid/whale-position", {}),
    ("whale_alert", "/api/hyperliquid/whale-alert", {}),
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse_json_text(value, fallback):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    if value is None:
        return fallback
    return value


def _normalize_source_type(source_type: Optional[str]) -> str:
    normalized = (source_type or MARKET_SIGNAL_SOURCE).strip() or MARKET_SIGNAL_SOURCE
    if normalized not in {MARKET_SIGNAL_SOURCE, WALLET_TRACKING_SOURCE}:
        raise HTTPException(status_code=400, detail="Invalid source_type")
    return normalized


def _normalize_source_config(source_type: str, source_config):
    parsed = _parse_json_text(source_config, {})
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="source_config must be an object")
    if source_type == MARKET_SIGNAL_SOURCE:
        return {}
    return parsed


def _parse_source_config_response(source_type: str, source_config):
    parsed = _parse_json_text(source_config, {})
    if not isinstance(parsed, dict):
        parsed = {}
    if source_type == MARKET_SIGNAL_SOURCE:
        return {}
    return parsed


def _build_pool_response(row) -> SignalPoolResponse:
    signal_ids = _parse_json_text(row[2], [])
    symbols = _parse_json_text(row[3], [])
    source_type = row[8] or MARKET_SIGNAL_SOURCE
    source_config = _parse_source_config_response(source_type, row[9])
    return SignalPoolResponse(
        id=row[0],
        pool_name=row[1],
        signal_ids=signal_ids or [],
        symbols=symbols or [],
        enabled=row[4],
        created_at=row[5],
        logic=row[6] or "OR",
        exchange=row[7] or "hyperliquid",
        source_type=source_type,
        source_config=source_config,
    )


def _count_active_wallet_pools(db: Session) -> int:
    value = db.execute(
        text("""
            SELECT COUNT(*)
            FROM signal_pools
            WHERE enabled = true
              AND (is_deleted IS NULL OR is_deleted = false)
              AND source_type = :source_type
        """),
        {"source_type": WALLET_TRACKING_SOURCE},
    ).scalar()
    return int(value or 0)


def _schedule_wallet_tracking_refresh() -> None:
    """CoinGlass wallet tracking is refreshed on demand by the status endpoint."""
    return None
