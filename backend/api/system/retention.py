"""Retention and collection-day system routes."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import SystemConfig

from .schemas import RetentionDaysRequest, RetentionDaysResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Config keys
HYPERLIQUID_RETENTION_KEY = "hyperliquid_retention_days"
BINANCE_RETENTION_KEY = "binance_retention_days"
HIBT_RETENTION_KEY = "hibt_retention_days"
DEFAULT_RETENTION_DAYS = 365


def get_retention_key(exchange: str) -> str:
    """Get the config key for a specific exchange"""
    if exchange == "binance":
        return BINANCE_RETENTION_KEY
    if exchange == "hibt":
        return HIBT_RETENTION_KEY
    return HYPERLIQUID_RETENTION_KEY


def get_retention_days(db: Session, exchange: str = "hyperliquid") -> int:
    """Get configured retention days from SystemConfig for specific exchange"""
    key = get_retention_key(exchange)
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config and config.value:
        try:
            return int(config.value)
        except ValueError:
            pass
    return DEFAULT_RETENTION_DAYS


def set_retention_days(db: Session, days: int, exchange: str = "hyperliquid") -> int:
    """Set retention days in SystemConfig for specific exchange"""
    key = get_retention_key(exchange)
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config:
        config.value = str(days)
    else:
        config = SystemConfig(
            key=key,
            value=str(days),
            description=f"{exchange.capitalize()} market data retention period in days",
        )
        db.add(config)
    db.commit()
    return days


@router.get("/retention-days")
def get_retention_days_api(exchange: str = "hyperliquid", db: Session = Depends(get_db)):
    """Get current retention days setting for specific exchange"""
    days = get_retention_days(db, exchange)
    return RetentionDaysResponse(days=days, exchange=exchange)


@router.put("/retention-days")
def update_retention_days(request: RetentionDaysRequest, db: Session = Depends(get_db)):
    """Update retention days setting for specific exchange"""
    if request.days < 7 or request.days > 730:
        raise HTTPException(status_code=400, detail="Retention days must be between 7 and 730")

    days = set_retention_days(db, request.days, request.exchange)
    logger.info(f"Updated {request.exchange} retention to {days} days")

    return RetentionDaysResponse(days=days, exchange=request.exchange)


@router.get("/collection-days")
def get_collection_days(exchange: str = "hyperliquid", db: Session = Depends(get_db)):
    """Get total days of market flow data collection for specific exchange.
    Calculated from earliest record timestamp to now.
    """
    try:
        query = text("SELECT MIN(timestamp) FROM market_trades_aggregated WHERE exchange = :exchange")
        result = db.execute(query, {"exchange": exchange}).scalar()

        if not result:
            return {"days": 0, "exchange": exchange}

        now_ms = int(time.time() * 1000)
        days = (now_ms - result) / (24 * 60 * 60 * 1000)
        return {"days": round(days, 1), "exchange": exchange}
    except Exception as e:
        logger.error(f"Failed to get collection days: {e}")
        return {"days": 0, "exchange": exchange}
