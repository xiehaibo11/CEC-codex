"""Static guards: the event paper trader seed script stays idempotent and wired to
the real creation service instead of duplicating its validation/fingerprint logic."""
from pathlib import Path

SEED_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_event_paper_trader.py"


def _source() -> str:
    return SEED_SCRIPT.read_text(encoding="utf-8")


def test_seed_script_exists():
    assert SEED_SCRIPT.is_file()


def test_idempotency_guard_present():
    src = _source()
    # Existing-trader-by-name check must come before any create/insert call.
    assert "EventContractPaperTrader" in src
    assert ".name == TRADER_NAME" in src
    guard_idx = src.index("existing is not None")
    create_idx = src.index("create_paper_trader(")
    assert guard_idx < create_idx


def test_strips_window_and_reviewer_weight_keys():
    src = _source()
    assert '"start_time"' in src
    assert '"end_time"' in src
    assert '"reviewer_weights"' in src
    # Keys must actually be removed from the config dict, not merely referenced.
    assert ".pop(key, None)" in src


def test_uses_create_paper_trader_service():
    src = _source()
    assert "from services.event_contract.paper_trader_api import create_paper_trader" in src
    assert "create_paper_trader(" in src


def test_default_run_id_and_seed_identity():
    src = _source()
    assert "850" in src
    assert "Reversal-08-23-UTC" in src
    assert "stake_amount=STAKE_AMOUNT" in src
    assert "STAKE_AMOUNT = 100.0" in src
    assert "INITIAL_BALANCE = 10000.0" in src
