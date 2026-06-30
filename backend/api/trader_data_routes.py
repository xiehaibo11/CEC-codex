"""
Trader Data Export/Import API Routes
Export AI decision logs with related Hyperliquid trades for migration between environments.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from database.connection import SessionLocal
from database.snapshot_connection import SnapshotSessionLocal
from .trader_data.export_service import build_export_response
from .trader_data.import_service import execute_import_data, preview_import_data
from .trader_data.schemas import ImportExecuteRequest, ImportPreviewRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trader", tags=["trader-data"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_snapshot_db():
    db = SnapshotSessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get("/{account_id}/export")
async def export_trader_data(
    account_id: int,
    db: Session = Depends(get_db),
    snapshot_db: Session = Depends(get_snapshot_db)
):
    """
    Export all AI decision logs with related Hyperliquid trades for a trader.
    Returns a JSON file for download.
    """
    return build_export_response(account_id, db, snapshot_db)


@router.post("/{account_id}/import/preview")
async def preview_import(
    account_id: int,
    request: ImportPreviewRequest,
    db: Session = Depends(get_db)
):
    """
    Preview import: analyze the data and return what will be imported/skipped.
    Also check if target account has prompt/signal bindings.
    """
    return preview_import_data(account_id, request.data, db)


@router.post("/{account_id}/import/execute")
async def execute_import(
    account_id: int,
    request: ImportExecuteRequest,
    db: Session = Depends(get_db),
    snapshot_db: Session = Depends(get_snapshot_db)
):
    """Execute the import: create decision logs and trades in both databases."""
    return execute_import_data(account_id, request.data, request.confirmed, db, snapshot_db)
