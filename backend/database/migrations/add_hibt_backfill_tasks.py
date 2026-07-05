"""Migration: Add HiBT K-line backfill task table.

Creates:
- hibt_backfill_tasks: Track manual HiBT K-line backfill task status/progress.
"""

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def upgrade():
    """Create hibt_backfill_tasks table with idempotency checks."""
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'hibt_backfill_tasks'
            )
        """))
        table_exists = result.scalar()

        if not table_exists:
            logger.info("[MIGRATION] Creating hibt_backfill_tasks table...")
            db.execute(text("""
                CREATE TABLE hibt_backfill_tasks (
                    id SERIAL PRIMARY KEY,
                    symbols VARCHAR(200) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    progress INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.execute(text("""
                CREATE INDEX ix_hibt_backfill_tasks_status
                ON hibt_backfill_tasks(status)
            """))
            db.commit()
            logger.info("[MIGRATION] hibt_backfill_tasks table created")
        else:
            logger.info("[MIGRATION] hibt_backfill_tasks table already exists, skipping")

        logger.info("Migration add_hibt_backfill_tasks completed successfully")
    except Exception as e:
        db.rollback()
        logger.error("Migration add_hibt_backfill_tasks failed: %s", e)
        raise
    finally:
        db.close()
