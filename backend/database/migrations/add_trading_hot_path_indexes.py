#!/usr/bin/env python3
"""
Migration: Add missing indexes on positions.account_id and
orders(account_id, status).

These columns back the dashboard's hottest polling queries
(GET /api/account/overview and /{account_id}/overview) and had no index,
causing full table scans that grow with the positions/orders tables.

Idempotent: uses CREATE INDEX IF NOT EXISTS (safe to re-run every startup).
Uses a short lock_timeout so it never blocks startup on a busy table.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal


def _set_startup_safe_timeouts(db) -> None:
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    db.execute(text("SET LOCAL statement_timeout = '120s'"))


def upgrade():
    """Apply the migration (idempotent)."""
    print("Starting migration: add_trading_hot_path_indexes")

    db = SessionLocal()
    try:
        _set_startup_safe_timeouts(db)

        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_positions_account_id "
            "ON positions (account_id)"
        ))
        print("  ensured ix_positions_account_id")

        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_orders_account_id_status "
            "ON orders (account_id, status)"
        ))
        print("  ensured ix_orders_account_id_status")

        db.commit()
        print("Migration completed: add_trading_hot_path_indexes")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()
