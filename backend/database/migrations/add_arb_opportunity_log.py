#!/usr/bin/env python3
"""Migration: create arb_opportunity_log table (idempotent).

Backs the Tier-1 price-locked delayed-settlement arbitrage OPPORTUNITY
DETECTOR MVP: one row per hypothetical 5-minute event-contract window that
became "price-locked" (sustained one-sided price beyond the minimum distance
from strike), settled in place at expiry so lock accuracy / daily opportunity
frequency can be read directly from the table. No venue quote columns yet -
the venue quote leg is a documented TODO pending a quote API.

Existence checks use the SQLAlchemy inspector and the id column is
dialect-aware so the same upgrade() runs against both the live Postgres and
sqlite-based tests.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from connection import SessionLocal

TABLE_DDL = """
    CREATE TABLE arb_opportunity_log (
        id {id_column},
        symbol VARCHAR(20) NOT NULL,
        window_start TIMESTAMP NOT NULL,
        strike FLOAT NOT NULL,
        direction VARCHAR(8) NOT NULL,
        locked_at TIMESTAMP NOT NULL,
        remaining_seconds INTEGER NOT NULL,
        distance_pct FLOAT NOT NULL,
        final_price FLOAT,
        outcome VARCHAR(8) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEXES = [
    ("idx_arb_opportunity_log_symbol", "arb_opportunity_log", "symbol"),
    ("idx_arb_opportunity_log_locked_at", "arb_opportunity_log", "locked_at"),
    ("idx_arb_opportunity_log_outcome", "arb_opportunity_log", "outcome"),
    ("idx_arb_opportunity_log_created_at", "arb_opportunity_log", "created_at"),
]

UNIQUE_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_arb_opportunity_symbol_window "
    "ON arb_opportunity_log(symbol, window_start)"
)


def upgrade() -> None:
    db = SessionLocal()
    try:
        bind = db.get_bind()
        if not inspect(bind).has_table("arb_opportunity_log"):
            id_column = (
                "SERIAL PRIMARY KEY" if bind.dialect.name == "postgresql" else "INTEGER PRIMARY KEY"
            )
            db.execute(text(TABLE_DDL.format(id_column=id_column)))
            db.commit()
        for index_name, table_name, column_name in INDEXES:
            db.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"))
        db.execute(text(UNIQUE_INDEX))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
