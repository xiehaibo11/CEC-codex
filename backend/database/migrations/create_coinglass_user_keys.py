"""Create per-user CoinGlass API key table."""

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def upgrade():
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        exists = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'coinglass_user_keys'
            )
        """)).scalar()

        if exists:
            logger.info("[MIGRATION] coinglass_user_keys table already exists, skipping")
            return

        logger.info("[MIGRATION] Creating coinglass_user_keys table...")
        db.execute(text("""
            CREATE TABLE coinglass_user_keys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                api_key_encrypted TEXT NOT NULL,
                key_masked VARCHAR(32),
                plan_level VARCHAR(50),
                expire_time BIGINT,
                expired BOOLEAN,
                last_validated_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_coinglass_user_keys_user UNIQUE (user_id)
            )
        """))
        db.execute(text("""
            CREATE INDEX ix_coinglass_user_keys_user_id
            ON coinglass_user_keys(user_id)
        """))
        db.commit()
        logger.info("[MIGRATION] coinglass_user_keys table created")
    except Exception as exc:
        db.rollback()
        logger.error("[MIGRATION] create_coinglass_user_keys failed: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
