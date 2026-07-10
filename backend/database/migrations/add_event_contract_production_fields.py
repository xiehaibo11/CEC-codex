#!/usr/bin/env python3
"""Add production execution and bar-deduplication fields to paper traders."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from connection import SessionLocal


TRADER_COLUMNS = {
    "execution_mode": "VARCHAR(10) NOT NULL DEFAULT 'paper'",
    "leverage": "DOUBLE PRECISION NOT NULL DEFAULT 10",
    "trade_margin": "DOUBLE PRECISION NOT NULL DEFAULT 100",
    "max_daily_trades": "INTEGER NOT NULL DEFAULT 10",
    "profit_target_multiplier": "DOUBLE PRECISION NOT NULL DEFAULT 2",
    "last_decision_time": "TIMESTAMP",
}


def _existing_columns(db) -> set[str]:
    rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'event_contract_paper_traders'
            """
        )
    )
    return {row[0] for row in rows}


def upgrade() -> None:
    db = SessionLocal()
    try:
        existing = _existing_columns(db)
        for column, ddl in TRADER_COLUMNS.items():
            if column in existing:
                continue
            db.execute(
                text(
                    f"ALTER TABLE event_contract_paper_traders "
                    f"ADD COLUMN {column} {ddl}"
                )
            )
        db.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_event_contract_paper_traders_last_decision_time "
                "ON event_contract_paper_traders (last_decision_time)"
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
