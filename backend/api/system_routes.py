"""System configuration and data management API routes."""

from fastapi import APIRouter

from api.system.backfill import (
    get_binance_backfill_status,
    get_hyperliquid_backfill_status,
    router as backfill_router,
    start_binance_backfill,
    start_hyperliquid_backfill,
)
from api.system.coverage import (
    get_data_coverage,
    get_expected_kline_records_per_day,
    router as coverage_router,
)
from api.system.retention import (
    BINANCE_RETENTION_KEY,
    DEFAULT_RETENTION_DAYS,
    HYPERLIQUID_RETENTION_KEY,
    get_collection_days,
    get_retention_days,
    get_retention_days_api,
    get_retention_key,
    router as retention_router,
    set_retention_days,
    update_retention_days,
)
from api.system.schemas import RetentionDaysRequest, RetentionDaysResponse
from api.system.storage_stats import get_storage_stats, router as storage_stats_router

router = APIRouter(prefix="/api/system", tags=["system"])
router.include_router(storage_stats_router)
router.include_router(coverage_router)
router.include_router(retention_router)
router.include_router(backfill_router)

__all__ = [
    "BINANCE_RETENTION_KEY",
    "DEFAULT_RETENTION_DAYS",
    "HYPERLIQUID_RETENTION_KEY",
    "RetentionDaysRequest",
    "RetentionDaysResponse",
    "get_binance_backfill_status",
    "get_collection_days",
    "get_data_coverage",
    "get_expected_kline_records_per_day",
    "get_hyperliquid_backfill_status",
    "get_retention_days",
    "get_retention_days_api",
    "get_retention_key",
    "get_storage_stats",
    "router",
    "set_retention_days",
    "start_binance_backfill",
    "start_hyperliquid_backfill",
    "update_retention_days",
]
