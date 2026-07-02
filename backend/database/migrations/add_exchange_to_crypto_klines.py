#!/usr/bin/env python3
"""
Migration: Add exchange field to crypto_klines table for multi-exchange support

This migration adds an 'exchange' field to the crypto_klines table to support
data from multiple exchanges (hyperliquid, binance, okx, etc.).

Changes:
1. Add 'exchange' column with default value 'hyperliquid'
2. Update unique constraint to include exchange field
3. Create index on exchange field for performance
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal, engine


EXCHANGE_UNIQUE_COLUMNS = ("exchange", "symbol", "market", "period", "timestamp")
FINAL_ENV_UNIQUE_COLUMNS = ("exchange", "symbol", "market", "period", "timestamp", "environment")


def _column_names(db) -> set[str]:
    result = db.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'crypto_klines'
    """))
    return {row[0] for row in result}


def _unique_constraints(db) -> dict[tuple[str, ...], list[str]]:
    result = db.execute(text("""
        SELECT con.conname,
               array_agg(att.attname ORDER BY ord.ordinality) AS column_names
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS ord(attnum, ordinality) ON true
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ord.attnum
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'crypto_klines'
          AND con.contype = 'u'
        GROUP BY con.oid, con.conname
    """))

    constraints: dict[tuple[str, ...], list[str]] = {}
    for row in result:
        constraints.setdefault(tuple(row[1]), []).append(row[0])
    return constraints


def _set_startup_safe_timeouts(db) -> None:
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    db.execute(text("SET LOCAL statement_timeout = '120s'"))


def upgrade():
    """Apply the migration (idempotent - safe to run multiple times)"""
    print("Starting migration: add_exchange_to_crypto_klines")

    db = SessionLocal()
    try:
        columns = _column_names(db)
        exchange_exists = "exchange" in columns
        environment_exists = "environment" in columns

        if exchange_exists and environment_exists:
            print("  ✓ Exchange and environment columns already exist; environment migration owns final constraint")
            db.commit()
            return

        unique_constraints = _unique_constraints(db)
        if exchange_exists and EXCHANGE_UNIQUE_COLUMNS in unique_constraints:
            print("  ✓ Exchange schema already exists, skipping locking DDL")
            db.commit()
            return

        _set_startup_safe_timeouts(db)

        if not exchange_exists:
            # Add exchange column with default value
            print("Adding exchange column to crypto_klines table...")
            db.execute(text("""
                ALTER TABLE crypto_klines
                ADD COLUMN exchange VARCHAR(20) NOT NULL DEFAULT 'hyperliquid'
            """))
            print("  ✓ Exchange column added")
        else:
            print("  ✓ Exchange column already exists, skipping")

        # Step 2: Create index on exchange field (idempotent)
        print("Creating index on exchange field...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_crypto_klines_exchange ON crypto_klines(exchange)
        """))

        if environment_exists or FINAL_ENV_UNIQUE_COLUMNS in _unique_constraints(db):
            print("  ✓ Environment schema is present, skipping legacy exchange-only constraint")
            db.commit()
            return

        # Step 3: Drop old unique constraint (idempotent)
        print("Dropping old unique constraint...")
        db.execute(text("""
            ALTER TABLE crypto_klines
            DROP CONSTRAINT IF EXISTS crypto_klines_symbol_market_period_timestamp_key
        """))

        # Step 4: Create new unique constraint including exchange (idempotent)
        print("Creating new unique constraint with exchange field...")
        if EXCHANGE_UNIQUE_COLUMNS not in _unique_constraints(db):
            db.execute(text("""
                ALTER TABLE crypto_klines
                ADD CONSTRAINT uq_crypto_klines_ex_sym_market_period_ts
                UNIQUE (exchange, symbol, market, period, timestamp)
            """))
            print("  ✓ New unique constraint created")
        else:
            print("  ✓ Unique constraint already exists, skipping")

        db.commit()
        print("Migration completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


def downgrade():
    """Rollback the migration"""
    print("Starting rollback: add_exchange_to_crypto_klines")

    db = SessionLocal()
    try:
        # Step 1: Drop new unique constraint
        print("Dropping new unique constraint...")
        db.execute(text("""
            ALTER TABLE crypto_klines
            DROP CONSTRAINT IF EXISTS crypto_klines_exchange_symbol_market_period_timestamp_key
        """))

        # Step 2: Recreate old unique constraint
        print("Recreating old unique constraint...")
        db.execute(text("""
            ALTER TABLE crypto_klines
            ADD CONSTRAINT crypto_klines_symbol_market_period_timestamp_key
            UNIQUE (symbol, market, period, timestamp)
        """))

        # Step 3: Drop index
        print("Dropping exchange index...")
        db.execute(text("""
            DROP INDEX IF EXISTS idx_crypto_klines_exchange
        """))

        # Step 4: Drop exchange column
        print("Dropping exchange column...")
        db.execute(text("""
            ALTER TABLE crypto_klines DROP COLUMN IF EXISTS exchange
        """))

        db.commit()
        print("Rollback completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Crypto Klines Exchange Migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    if args.rollback:
        downgrade()
    else:
        upgrade()
