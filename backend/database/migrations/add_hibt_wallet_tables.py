"""Migration: Add HiBT wallet table.

Creates:
- hibt_wallets: Store HiBT perpetual futures API credentials per AI Trader per environment.
"""

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def upgrade():
    """Create HiBT wallet table with idempotency checks."""
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'hibt_wallets'
            )
        """))
        wallets_exists = result.scalar()

        if not wallets_exists:
            logger.info("[MIGRATION] Creating hibt_wallets table...")
            db.execute(text("""
                CREATE TABLE hibt_wallets (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    environment VARCHAR(20) NOT NULL,
                    access_key_encrypted VARCHAR(500) NOT NULL,
                    secret_key_encrypted VARCHAR(500) NOT NULL,
                    max_leverage INTEGER NOT NULL DEFAULT 20,
                    default_leverage INTEGER NOT NULL DEFAULT 1,
                    is_active VARCHAR(10) NOT NULL DEFAULT 'true',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_hibt_wallets_account_environment
                        UNIQUE (account_id, environment)
                )
            """))
            db.execute(text("""
                CREATE INDEX ix_hibt_wallets_account_id
                ON hibt_wallets(account_id)
            """))
            db.commit()
            logger.info("[MIGRATION] hibt_wallets table created")
        else:
            logger.info("[MIGRATION] hibt_wallets table already exists, skipping")

        logger.info("Migration add_hibt_wallet_tables completed successfully")
    except Exception as e:
        db.rollback()
        logger.error("Migration add_hibt_wallet_tables failed: %s", e)
        raise
    finally:
        db.close()
