"""ORM must cover every column _persist_backtest writes."""
from database.models.event_contract import EventContractTradeLog

REQUIRED = {
    "consensus_source", "ai_participated", "ai_model", "ai_account_name",
    "signal_time", "signal_type", "event_signal",
    "entry_delay_lag_seconds", "expiry_lag_seconds",
}


def test_orm_has_all_persisted_columns():
    columns = {c.name for c in EventContractTradeLog.__table__.columns}
    missing = REQUIRED - columns
    assert not missing, f"ORM missing columns: {missing}"
