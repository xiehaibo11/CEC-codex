"""Add persistent event-contract backtest task table."""

import logging
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import engine

logger = logging.getLogger(__name__)


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_contract_backtest_tasks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                run_id INTEGER REFERENCES event_contract_backtest_runs(id) ON DELETE SET NULL,
                name VARCHAR(200),
                status VARCHAR(30) NOT NULL DEFAULT 'pending',
                symbol VARCHAR(20) NOT NULL,
                exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
                environment VARCHAR(20) NOT NULL DEFAULT 'mainnet',
                period VARCHAR(10) NOT NULL DEFAULT '1m',
                config TEXT,
                progress_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
                phase VARCHAR(60),
                processed_decision_bars INTEGER NOT NULL DEFAULT 0,
                total_decision_bars INTEGER NOT NULL DEFAULT 0,
                completed_ai_reviews INTEGER NOT NULL DEFAULT 0,
                expected_ai_reviews INTEGER NOT NULL DEFAULT 0,
                ai_reviewer_statuses TEXT,
                latest_message TEXT,
                error_message TEXT,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_tasks_status ON event_contract_backtest_tasks(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_tasks_user ON event_contract_backtest_tasks(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_tasks_created ON event_contract_backtest_tasks(created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_tasks_run ON event_contract_backtest_tasks(run_id)"))

    logger.info("Migration completed: event contract backtest task table ready")


def downgrade():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS event_contract_backtest_tasks CASCADE"))


if __name__ == "__main__":
    upgrade()
