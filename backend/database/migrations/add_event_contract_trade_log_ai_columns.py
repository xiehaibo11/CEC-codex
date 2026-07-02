#!/usr/bin/env python3
"""Migration: add AI/timing columns to event_contract_trade_logs (idempotent)."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal

COLUMNS = {
    "consensus_source": "VARCHAR(30)",
    "ai_participated": "BOOLEAN NOT NULL DEFAULT FALSE",
    "ai_model": "VARCHAR(100)",
    "ai_account_name": "VARCHAR(100)",
    "signal_time": "TIMESTAMP",
    "signal_type": "VARCHAR(50)",
    "event_signal": "TEXT",
    "entry_delay_lag_seconds": "INTEGER NOT NULL DEFAULT 0",
    "expiry_lag_seconds": "INTEGER NOT NULL DEFAULT 0",
}


def _existing_columns(db) -> set:
    result = db.execute(text(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'event_contract_trade_logs'
        """
    ))
    return {row[0] for row in result}


def upgrade() -> None:
    db = SessionLocal()
    try:
        existing = _existing_columns(db)
        for name, ddl in COLUMNS.items():
            if name in existing:
                continue
            db.execute(text(f"ALTER TABLE event_contract_trade_logs ADD COLUMN {name} {ddl}"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
