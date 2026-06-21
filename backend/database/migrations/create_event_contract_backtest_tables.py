"""Create event contract backtest tables."""

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
            CREATE TABLE IF NOT EXISTS event_contract_backtest_runs (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
                environment VARCHAR(20) NOT NULL DEFAULT 'mainnet',
                period VARCHAR(10) NOT NULL DEFAULT '1m',
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                config TEXT,
                summary TEXT,
                equity_curve TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'completed',
                error_message TEXT,
                total_trades INTEGER NOT NULL DEFAULT 0,
                win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
                final_equity DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_contract_trade_logs (
                id SERIAL PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES event_contract_backtest_runs(id) ON DELETE CASCADE,
                trade_index INTEGER NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                direction VARCHAR(10) NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                entry_price DOUBLE PRECISION NOT NULL,
                expiry_time TIMESTAMP NOT NULL,
                expiry_price DOUBLE PRECISION NOT NULL,
                result VARCHAR(10) NOT NULL,
                profit_loss DOUBLE PRECISION NOT NULL DEFAULT 0,
                signal_strength DOUBLE PRECISION,
                ai_consensus_rate DOUBLE PRECISION,
                consensus_source VARCHAR(30),
                ai_participated BOOLEAN DEFAULT FALSE,
                ai_model VARCHAR(120),
                ai_account_name VARCHAR(120),
                signal_time TIMESTAMP,
                signal_type VARCHAR(50),
                event_signal TEXT,
                entry_delay_lag_seconds INTEGER DEFAULT 0,
                expiry_lag_seconds INTEGER DEFAULT 0,
                long_votes INTEGER,
                short_votes INTEGER,
                hold_votes INTEGER,
                market_state VARCHAR(50),
                trap_risk DOUBLE PRECISION,
                fake_breakout_risk DOUBLE PRECISION,
                reason TEXT,
                factor_snapshot TEXT,
                ai_decision_snapshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_runs_symbol ON event_contract_backtest_runs(symbol)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_runs_exchange ON event_contract_backtest_runs(exchange)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_runs_created ON event_contract_backtest_runs(created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_trades_run ON event_contract_trade_logs(run_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_trades_entry ON event_contract_trade_logs(entry_time)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_contract_trades_result ON event_contract_trade_logs(result)"))

    logger.info("Migration completed: event contract backtest tables ready")


def downgrade():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS event_contract_trade_logs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS event_contract_backtest_runs CASCADE"))


if __name__ == "__main__":
    upgrade()
