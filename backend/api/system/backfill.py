"""Backfill system routes."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db

from .retention import get_retention_days

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/binance/backfill")
async def start_binance_backfill(
    force: bool = False,
    db: Session = Depends(get_db),
):
    """Start Binance historical data backfill task.
    Uses current Binance watchlist symbols.
    Backfills: K-lines for configured retention days, OI (real-time only),
    Funding (365d), Sentiment (30d).

    Args:
        force: If True, cancel any running/pending tasks and start fresh
    """
    from database.models import BinanceBackfillTask
    from services.binance_symbol_service import get_selected_symbols as get_binance_selected_symbols
    from services.exchanges.binance_backfill import binance_backfill_service

    # Check if already running
    running_task = db.query(BinanceBackfillTask).filter(
        BinanceBackfillTask.status.in_(["pending", "running"])
    ).first()

    if running_task:
        if force:
            # Cancel all running/pending tasks
            db.query(BinanceBackfillTask).filter(
                BinanceBackfillTask.status.in_(["pending", "running"])
            ).update({"status": "cancelled"})
            db.commit()
        else:
            raise HTTPException(status_code=400, detail="A backfill task is already running")

    # Get Binance watchlist symbols
    symbols = get_binance_selected_symbols()
    if not symbols:
        symbols = ["BTC"]
    retention_days = get_retention_days(db, "binance")
    logger.info(f"[Binance] Starting backfill with symbols: {symbols}")

    # Create task
    task = BinanceBackfillTask(
        symbols=",".join(symbols),
        status="pending",
        progress=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Start backfill in background
    asyncio.create_task(binance_backfill_service.start_backfill(task.id))

    return {
        "task_id": task.id,
        "symbols": symbols,
        "retention_days": retention_days,
        "status": "started",
    }


@router.get("/binance/backfill/status")
def get_binance_backfill_status(db: Session = Depends(get_db)):
    """Get current Binance backfill task status."""
    from database.models import BinanceBackfillTask

    # Get most recent task
    task = db.query(BinanceBackfillTask).order_by(
        BinanceBackfillTask.created_at.desc()
    ).first()

    if not task:
        return {"status": "none", "progress": 0}

    return {
        "task_id": task.id,
        "symbols": task.symbols.split(",") if task.symbols else [],
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.post("/hyperliquid/backfill")
async def start_hyperliquid_backfill(
    force: bool = False,
    db: Session = Depends(get_db),
):
    """Start Hyperliquid K-line backfill task.
    Uses current watchlist symbols.
    Backfills: K-lines (~5000 records, ~3.5 days per symbol).

    Args:
        force: If True, cancel any running/pending tasks and start fresh
    """
    from database.models import HyperliquidBackfillTask
    from services.hyperliquid_symbol_service import get_selected_symbols
    from services.exchanges.hyperliquid_backfill import hyperliquid_backfill_service

    # Check if already running
    running_task = db.query(HyperliquidBackfillTask).filter(
        HyperliquidBackfillTask.status.in_(["pending", "running"])
    ).first()
    if running_task:
        if force:
            db.query(HyperliquidBackfillTask).filter(
                HyperliquidBackfillTask.status.in_(["pending", "running"])
            ).update({"status": "cancelled"})
            db.commit()
        else:
            raise HTTPException(status_code=400, detail="A backfill task is already running")

    # Get watchlist symbols
    symbols = get_selected_symbols()
    if not symbols:
        symbols = ["BTC"]

    # Create task
    task = HyperliquidBackfillTask(
        symbols=",".join(symbols),
        status="pending",
        progress=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Start backfill in background
    asyncio.create_task(hyperliquid_backfill_service.start_backfill(task.id))

    return {
        "task_id": task.id,
        "symbols": symbols,
        "status": "started",
    }


@router.get("/hyperliquid/backfill/status")
def get_hyperliquid_backfill_status(db: Session = Depends(get_db)):
    """Get current Hyperliquid backfill task status."""
    from database.models import HyperliquidBackfillTask

    # Get most recent task
    task = db.query(HyperliquidBackfillTask).order_by(
        HyperliquidBackfillTask.created_at.desc()
    ).first()

    if not task:
        return {"status": "none", "progress": 0}

    return {
        "task_id": task.id,
        "symbols": task.symbols.split(",") if task.symbols else [],
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.post("/hibt/backfill")
async def start_hibt_backfill(
    force: bool = False,
    db: Session = Depends(get_db),
):
    """Start a HiBT K-line backfill task using the current HiBT watchlist.

    Backfills recent candles (up to 500 rows per symbol/period) for a few
    periods into ``crypto_klines``. HiBT's candle endpoint has no deep history,
    so this is a recent-window backfill.

    Args:
        force: If True, cancel any running/pending tasks and start fresh.
    """
    from database.models import HibtBackfillTask
    from services.exchanges.hibt_backfill import hibt_backfill_service
    from services.hibt_symbol_service import get_selected_symbols as get_hibt_selected_symbols

    running_task = db.query(HibtBackfillTask).filter(
        HibtBackfillTask.status.in_(["pending", "running"])
    ).first()
    if running_task:
        if force:
            db.query(HibtBackfillTask).filter(
                HibtBackfillTask.status.in_(["pending", "running"])
            ).update({"status": "cancelled"})
            db.commit()
        else:
            raise HTTPException(status_code=400, detail="A backfill task is already running")

    symbols = get_hibt_selected_symbols()
    if not symbols:
        symbols = ["BTC"]
    logger.info("[HiBT] Starting backfill with symbols: %s", symbols)

    task = HibtBackfillTask(
        symbols=",".join(symbols),
        status="pending",
        progress=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Start backfill in background
    asyncio.create_task(hibt_backfill_service.start_backfill(task.id))

    return {
        "task_id": task.id,
        "symbols": symbols,
        "status": "started",
    }


@router.get("/hibt/backfill/status")
def get_hibt_backfill_status(db: Session = Depends(get_db)):
    """Get current HiBT backfill task status."""
    from database.models import HibtBackfillTask

    task = db.query(HibtBackfillTask).order_by(
        HibtBackfillTask.created_at.desc()
    ).first()

    if not task:
        return {"status": "none", "progress": 0}

    return {
        "task_id": task.id,
        "symbols": task.symbols.split(",") if task.symbols else [],
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
