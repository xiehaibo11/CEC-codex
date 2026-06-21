"""Add event signal fields to event contract trade logs."""

import logging
import os
import sys

from sqlalchemy import inspect, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import engine

logger = logging.getLogger(__name__)


def _add_column(conn, table: str, column: str, ddl: str):
    inspector = inspect(conn)
    columns = {item["name"] for item in inspector.get_columns(table)}
    if column in columns:
        logger.info("Column %s already exists in %s, skipping", column, table)
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    logger.info("Added column %s to %s", column, table)


def upgrade():
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "event_contract_trade_logs" not in inspector.get_table_names():
            logger.info("event_contract_trade_logs does not exist yet, skipping")
            return
        _add_column(conn, "event_contract_trade_logs", "signal_type", "signal_type VARCHAR(50)")
        _add_column(conn, "event_contract_trade_logs", "event_signal", "event_signal TEXT")
    logger.info("Migration completed: event contract signal fields ready")


def downgrade():
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    upgrade()
