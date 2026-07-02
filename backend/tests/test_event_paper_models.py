"""Schema + migration coverage for the event contract paper trader tables."""
import importlib

from database.models.event_contract import EventContractPaperTrader, EventContractPaperBet

TRADER_REQUIRED_COLUMNS = {
    "id", "name", "enabled", "symbol", "exchange", "environment", "config",
    "stake_amount", "initial_balance", "current_balance", "strategy_fingerprint",
    "created_at", "updated_at",
}

BET_REQUIRED_COLUMNS = {
    "id", "trader_id", "direction", "status", "decision_time", "entry_time",
    "entry_price", "expiry_time", "expiry_price", "result", "pnl", "stake",
    "payout_ratio", "market_state", "signal_strength", "reason",
    "analysis_snapshot", "created_at", "updated_at",
}


def test_paper_trader_orm_has_required_columns():
    columns = {c.name for c in EventContractPaperTrader.__table__.columns}
    missing = TRADER_REQUIRED_COLUMNS - columns
    assert not missing, f"EventContractPaperTrader missing columns: {missing}"


def test_paper_bet_orm_has_required_columns():
    columns = {c.name for c in EventContractPaperBet.__table__.columns}
    missing = BET_REQUIRED_COLUMNS - columns
    assert not missing, f"EventContractPaperBet missing columns: {missing}"


def test_paper_bet_status_default_and_values():
    status_col = EventContractPaperBet.__table__.columns["status"]
    assert status_col.default.arg == "pending_entry"
    # Allowed values per spec: pending_entry|open|settled (enforced at service layer,
    # not a DB CHECK constraint — document the contract here).
    allowed = {"pending_entry", "open", "settled"}
    assert status_col.default.arg in allowed


def test_paper_bet_trader_fk_cascades_on_delete():
    trader_id_col = EventContractPaperBet.__table__.columns["trader_id"]
    fks = list(trader_id_col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "event_contract_paper_traders"
    assert fks[0].ondelete == "CASCADE"


def test_paper_trader_name_is_unique():
    name_col = EventContractPaperTrader.__table__.columns["name"]
    assert name_col.unique is True


def test_migration_upgrade_is_idempotent():
    """upgrade() must be safe to run repeatedly against the live dev postgres."""
    migration = importlib.import_module("database.migrations.add_event_contract_paper_tables")
    migration.upgrade()
    migration.upgrade()


def test_migration_registered_last_in_migration_manager():
    migration_manager = importlib.import_module("database.migration_manager")
    assert migration_manager.MIGRATIONS[-1] == "add_event_contract_paper_tables.py"
