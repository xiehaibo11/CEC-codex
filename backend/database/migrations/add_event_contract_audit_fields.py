"""Add audit fields to event contract trade logs."""

import logging
import os
import sys

from sqlalchemy import inspect, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import engine

logger = logging.getLogger(__name__)


def _add_column(conn, table_name: str, column_name: str, ddl: str, existing: set[str]):
    if column_name in existing:
        logger.info("Column %s already exists in %s, skipping", column_name, table_name)
        return
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
    logger.info("Added column %s to %s", column_name, table_name)


def upgrade():
    table_name = "event_contract_trade_logs"
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table(table_name):
            logger.info("Table %s does not exist yet, skipping audit-field migration", table_name)
            return

        existing = {column["name"] for column in inspector.get_columns(table_name)}
        _add_column(conn, table_name, "consensus_source", "VARCHAR(30)", existing)
        _add_column(conn, table_name, "ai_participated", "BOOLEAN DEFAULT FALSE", existing)
        _add_column(conn, table_name, "ai_model", "VARCHAR(120)", existing)
        _add_column(conn, table_name, "ai_account_name", "VARCHAR(120)", existing)
        _add_column(conn, table_name, "signal_time", "TIMESTAMP", existing)
        _add_column(conn, table_name, "entry_delay_lag_seconds", "INTEGER DEFAULT 0", existing)
        _add_column(conn, table_name, "expiry_lag_seconds", "INTEGER DEFAULT 0", existing)

    logger.info("Migration completed: event contract audit fields ready")


def downgrade():
    with engine.begin() as conn:
        for column_name in (
            "expiry_lag_seconds",
            "entry_delay_lag_seconds",
            "signal_time",
            "ai_account_name",
            "ai_model",
            "ai_participated",
            "consensus_source",
        ):
            conn.execute(text(f"ALTER TABLE event_contract_trade_logs DROP COLUMN IF EXISTS {column_name}"))


if __name__ == "__main__":
    upgrade()
