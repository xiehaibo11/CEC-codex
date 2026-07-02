#!/usr/bin/env python3
"""Migration: create event_contract_validation_log table (idempotent).

Backs the rolling out-of-sample validation cycle (spec module 4): one row per
frozen-parameter holdout window appended automatically for a strategy
fingerprint, so cumulative significance can be read without manually
triggering the holdout endpoint.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal

TABLE_DDL = """
    CREATE TABLE event_contract_validation_log (
        id SERIAL PRIMARY KEY,
        strategy_fingerprint VARCHAR(32) NOT NULL,
        source_run_id INTEGER,
        holdout_run_id INTEGER,
        task_id INTEGER,
        window_start TIMESTAMP,
        window_end TIMESTAMP,
        decided INTEGER,
        wins INTEGER,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEXES = [
    ("idx_event_contract_validation_log_fingerprint", "event_contract_validation_log", "strategy_fingerprint"),
    ("idx_event_contract_validation_log_holdout_run_id", "event_contract_validation_log", "holdout_run_id"),
    ("idx_event_contract_validation_log_status", "event_contract_validation_log", "status"),
    ("idx_event_contract_validation_log_task_id", "event_contract_validation_log", "task_id"),
    ("idx_event_contract_validation_log_window_end", "event_contract_validation_log", "window_end"),
]


def _existing_tables(db) -> set:
    result = db.execute(text(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'event_contract_validation_log'
        """
    ))
    return {row[0] for row in result}


def upgrade() -> None:
    db = SessionLocal()
    try:
        if "event_contract_validation_log" not in _existing_tables(db):
            db.execute(text(TABLE_DDL))
            db.commit()
        for index_name, table_name, column_name in INDEXES:
            db.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
