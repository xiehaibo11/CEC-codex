#!/usr/bin/env python3
"""
Migration: Add environment field to crypto_klines table for testnet/mainnet isolation

This migration adds an 'environment' field to the crypto_klines table to support
proper isolation between testnet and mainnet K-line data.

Changes:
1. Add 'environment' column with default value 'mainnet'
2. Update all existing records to 'mainnet' (since current hardcoded sandbox=False)
3. Update unique constraint to include environment field
4. Create indexes on environment field for performance

Background:
Previously, HyperliquidClient was hardcoded with sandbox=False, meaning all K-line
data came from mainnet regardless of account environment. This migration enables
proper environment isolation for GitHub users upgrading their installations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal, engine


FINAL_UNIQUE_COLUMNS = ("exchange", "symbol", "market", "period", "timestamp", "environment")
LEGACY_EXCHANGE_UNIQUE_COLUMNS = ("exchange", "symbol", "market", "period", "timestamp")


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


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _set_startup_safe_timeouts(db) -> None:
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    db.execute(text("SET LOCAL statement_timeout = '120s'"))


def _drop_unique_constraints_by_columns(db, columns: tuple[str, ...]) -> None:
    for constraint_name in _unique_constraints(db).get(columns, []):
        print(f"Dropping legacy unique constraint: {constraint_name}")
        db.execute(text(
            f"ALTER TABLE crypto_klines DROP CONSTRAINT IF EXISTS {_quote_identifier(constraint_name)}"
        ))


def upgrade():
    """Apply the migration"""
    print("Starting migration: add_environment_to_crypto_klines")

    db = SessionLocal()
    try:
        columns = _column_names(db)
        unique_constraints = _unique_constraints(db)
        exchange_exists = "exchange" in columns
        environment_exists = "environment" in columns

        if (
            exchange_exists
            and environment_exists
            and FINAL_UNIQUE_COLUMNS in unique_constraints
        ):
            print("  ✓ Environment schema already exists, skipping locking DDL")
            db.commit()
            return

        _set_startup_safe_timeouts(db)

        # Step 1: Add environment column with default value (idempotent)
        if not environment_exists:
            print("Adding environment column to crypto_klines table...")
            db.execute(text("""
                ALTER TABLE crypto_klines
                ADD COLUMN environment VARCHAR(20) NOT NULL DEFAULT 'mainnet'
            """))
        else:
            print("  ✓ Environment column already exists, skipping")

        # Step 2: Update all existing records to 'mainnet'
        # (since current hardcoded sandbox=False means all data is mainnet)
        if not environment_exists:
            print("Updating all existing records to 'mainnet' environment...")
            result = db.execute(text("""
                UPDATE crypto_klines SET environment = 'mainnet' WHERE environment IS NULL
            """))
            print(f"Updated {result.rowcount} records")

        if not exchange_exists:
            print("  ! Exchange column missing; final environment constraint will be created after exchange migration")
            db.commit()
            return

        # Step 3: Drop old unique constraint
        unique_constraints = _unique_constraints(db)
        if LEGACY_EXCHANGE_UNIQUE_COLUMNS in unique_constraints:
            _drop_unique_constraints_by_columns(db, LEGACY_EXCHANGE_UNIQUE_COLUMNS)

        # Step 4: Create new unique constraint including environment (idempotent)
        if FINAL_UNIQUE_COLUMNS not in _unique_constraints(db):
            print("Creating new unique constraint with environment field...")
            db.execute(text("""
                ALTER TABLE crypto_klines
                ADD CONSTRAINT uq_crypto_klines_ex_sym_market_period_ts_env
                UNIQUE (exchange, symbol, market, period, timestamp, environment)
            """))
            print("  ✓ New unique constraint created")
        else:
            print("  ✓ Unique constraint already exists, skipping")

        # Step 5: Create indexes for performance (idempotent)
        print("Creating performance indexes...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_crypto_klines_environment ON crypto_klines(environment)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_crypto_klines_symbol_period_env ON crypto_klines(symbol, period, environment)
        """))

        db.commit()
        print("Migration completed successfully!")
        print("All existing K-line data has been marked as 'mainnet' environment")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


def downgrade():
    """Rollback the migration"""
    print("Starting rollback: add_environment_to_crypto_klines")

    db = SessionLocal()
    try:
        # Step 1: Drop new unique constraint
        print("Dropping new unique constraint...")
        db.execute(text("""
            ALTER TABLE crypto_klines
            DROP CONSTRAINT IF EXISTS crypto_klines_exchange_symbol_market_period_timestamp_environment_key
        """))

        # Step 2: Recreate old unique constraint
        print("Recreating old unique constraint...")
        db.execute(text("""
            ALTER TABLE crypto_klines
            ADD CONSTRAINT crypto_klines_exchange_symbol_market_period_timestamp_key
            UNIQUE (exchange, symbol, market, period, timestamp)
        """))

        # Step 3: Drop performance indexes
        print("Dropping performance indexes...")
        db.execute(text("""
            DROP INDEX IF EXISTS idx_crypto_klines_environment
        """))
        db.execute(text("""
            DROP INDEX IF EXISTS idx_crypto_klines_symbol_period_env
        """))

        # Step 4: Drop environment column
        print("Dropping environment column...")
        db.execute(text("""
            ALTER TABLE crypto_klines DROP COLUMN IF EXISTS environment
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
    parser = argparse.ArgumentParser(description='Crypto Klines Environment Migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    if args.rollback:
        downgrade()
    else:
        upgrade()
