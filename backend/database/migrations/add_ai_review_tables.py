#!/usr/bin/env python3
"""Create AI review tables and decision-log review columns."""
from __future__ import annotations

import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import engine  # noqa: E402


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(result.scalar())


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return bool(result.scalar())


def upgrade() -> None:
    with engine.connect() as conn:
        if not _table_exists(conn, "ai_review_runs"):
            conn.execute(
                text(
                    """
                    CREATE TABLE ai_review_runs (
                        id SERIAL PRIMARY KEY,
                        account_id INTEGER NOT NULL REFERENCES accounts(id),
                        decision_log_id INTEGER REFERENCES ai_decision_logs(id),
                        exchange VARCHAR(20),
                        environment VARCHAR(20),
                        symbol VARCHAR(20),
                        operation VARCHAR(10) NOT NULL,
                        original_target_portion DECIMAL(10, 6),
                        original_leverage INTEGER,
                        verdict VARCHAR(20) NOT NULL,
                        final_target_portion DECIMAL(10, 6),
                        final_leverage INTEGER,
                        final_reason TEXT,
                        latency_ms INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
        if not _table_exists(conn, "ai_review_agent_reports"):
            conn.execute(
                text(
                    """
                    CREATE TABLE ai_review_agent_reports (
                        id SERIAL PRIMARY KEY,
                        review_run_id INTEGER NOT NULL REFERENCES ai_review_runs(id),
                        agent_role VARCHAR(50) NOT NULL,
                        verdict VARCHAR(20) NOT NULL,
                        confidence DECIMAL(5, 4),
                        report_json TEXT,
                        report_text TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
        for column, ddl in (
            ("review_run_id", "ALTER TABLE ai_decision_logs ADD COLUMN review_run_id INTEGER"),
            ("review_verdict", "ALTER TABLE ai_decision_logs ADD COLUMN review_verdict VARCHAR(20)"),
            ("review_blocked_reason", "ALTER TABLE ai_decision_logs ADD COLUMN review_blocked_reason TEXT"),
        ):
            if not _column_exists(conn, "ai_decision_logs", column):
                conn.execute(text(ddl))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_ai_review_runs_account_id ON ai_review_runs(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_review_runs_symbol ON ai_review_runs(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_ai_review_runs_verdict ON ai_review_runs(verdict)",
            "CREATE INDEX IF NOT EXISTS idx_ai_review_agent_reports_run_id ON ai_review_agent_reports(review_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decision_logs_review_run_id ON ai_decision_logs(review_run_id)",
        ):
            conn.execute(text(stmt))
        conn.commit()


if __name__ == "__main__":
    upgrade()
