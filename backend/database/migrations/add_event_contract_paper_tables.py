#!/usr/bin/env python3
"""Migration: create event_contract_paper_traders / event_contract_paper_bets tables (idempotent)."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal

TRADER_TABLE_DDL = """
    CREATE TABLE event_contract_paper_traders (
        id SERIAL PRIMARY KEY,
        name VARCHAR(200) NOT NULL UNIQUE,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        symbol VARCHAR(20) NOT NULL DEFAULT 'BTC',
        exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
        environment VARCHAR(20) NOT NULL DEFAULT 'mainnet',
        config TEXT,
        stake_amount DOUBLE PRECISION NOT NULL DEFAULT 100,
        initial_balance DOUBLE PRECISION NOT NULL DEFAULT 10000,
        current_balance DOUBLE PRECISION NOT NULL DEFAULT 10000,
        strategy_fingerprint VARCHAR(32),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

BET_TABLE_DDL = """
    CREATE TABLE event_contract_paper_bets (
        id SERIAL PRIMARY KEY,
        trader_id INTEGER NOT NULL REFERENCES event_contract_paper_traders(id) ON DELETE CASCADE,
        direction VARCHAR(10) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending_entry',
        decision_time TIMESTAMP NOT NULL,
        entry_time TIMESTAMP,
        entry_price DOUBLE PRECISION,
        expiry_time TIMESTAMP,
        expiry_price DOUBLE PRECISION,
        result VARCHAR(10),
        pnl DOUBLE PRECISION,
        stake DOUBLE PRECISION NOT NULL,
        payout_ratio DOUBLE PRECISION NOT NULL,
        market_state VARCHAR(50),
        signal_strength DOUBLE PRECISION,
        reason TEXT,
        analysis_snapshot TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEXES = [
    ("idx_event_contract_paper_traders_symbol", "event_contract_paper_traders", "symbol"),
    ("idx_event_contract_paper_traders_exchange", "event_contract_paper_traders", "exchange"),
    ("idx_event_contract_paper_traders_environment", "event_contract_paper_traders", "environment"),
    ("idx_event_contract_paper_traders_fingerprint", "event_contract_paper_traders", "strategy_fingerprint"),
    ("idx_event_contract_paper_traders_created_at", "event_contract_paper_traders", "created_at"),
    ("idx_event_contract_paper_bets_trader_id", "event_contract_paper_bets", "trader_id"),
    ("idx_event_contract_paper_bets_status", "event_contract_paper_bets", "status"),
    ("idx_event_contract_paper_bets_decision_time", "event_contract_paper_bets", "decision_time"),
    ("idx_event_contract_paper_bets_expiry_time", "event_contract_paper_bets", "expiry_time"),
    ("idx_event_contract_paper_bets_created_at", "event_contract_paper_bets", "created_at"),
]


def _existing_tables(db) -> set:
    result = db.execute(text(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('event_contract_paper_traders', 'event_contract_paper_bets')
        """
    ))
    return {row[0] for row in result}


def upgrade() -> None:
    db = SessionLocal()
    try:
        existing = _existing_tables(db)
        if "event_contract_paper_traders" not in existing:
            db.execute(text(TRADER_TABLE_DDL))
            db.commit()
        if "event_contract_paper_bets" not in existing:
            db.execute(text(BET_TABLE_DDL))
            db.commit()
        for index_name, table_name, column_name in INDEXES:
            db.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
