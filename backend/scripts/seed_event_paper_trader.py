"""Seed the first live event-contract paper trader from a validated backtest run.

Reads the stored ``config`` of an ``event_contract_backtest_runs`` row (run 850 by
default - the 75% target-win-rate reversal strategy this task deploys), strips the
backtest-window-specific keys (``start_time``/``end_time``/``reviewer_weights`` - the
live cycle recomputes its own window and reviewer weights every cycle via
``event_contract_service.predict``, see ``services/event_contract/backtest.py``), and
creates a ``EventContractPaperTrader`` row via
``services.event_contract.paper_trader_api.create_paper_trader`` so the 60s
``run_live_paper_cycle`` scheduler tick picks it up.

Idempotent: if a trader with the target name already exists, prints its id and exits
0 without creating a duplicate (matches ``create_paper_trader``'s duplicate-name guard,
but checked up front so re-running this script is a safe no-op).

Usage:
    uv run python scripts/seed_event_paper_trader.py [run_id]

``run_id`` defaults to 850.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from database.connection import SessionLocal  # noqa: E402
from database.models.event_contract import EventContractPaperTrader  # noqa: E402
from services.event_contract.paper_trader_api import create_paper_trader  # noqa: E402

TRADER_NAME = "Reversal-08-23-UTC"
STAKE_AMOUNT = 100.0
INITIAL_BALANCE = 10000.0

# Backtest-window-specific keys that must not leak into a live trader's config: the
# live cycle re-derives its own window and recomputes reviewer weights fresh on every
# tick (event_contract_service.predict -> _load_reviewer_weights), so carrying over the
# frozen backtest-time values would pin the trader to stale weights instead.
_STRIP_KEYS = ("start_time", "end_time", "reviewer_weights")


def _load_run_config(session, run_id: int) -> dict:
    row = session.execute(
        text("SELECT config FROM event_contract_backtest_runs WHERE id = :run_id"),
        {"run_id": run_id},
    ).first()
    if row is None:
        raise SystemExit(f"event_contract_backtest_runs.id={run_id} not found")
    raw = row[0]
    if not raw:
        raise SystemExit(f"event_contract_backtest_runs.id={run_id} has an empty config")
    return json.loads(raw)


def main() -> None:
    run_id = int(sys.argv[1]) if len(sys.argv) > 1 else 850

    session = SessionLocal()
    try:
        existing = (
            session.query(EventContractPaperTrader)
            .filter(EventContractPaperTrader.name == TRADER_NAME)
            .first()
        )
        if existing is not None:
            print(f"Paper trader '{TRADER_NAME}' already exists (id={existing.id}) - skipping")
            return

        config = _load_run_config(session, run_id)
        for key in _STRIP_KEYS:
            config.pop(key, None)

        trader = create_paper_trader(
            session,
            name=TRADER_NAME,
            config=config,
            stake_amount=STAKE_AMOUNT,
            initial_balance=INITIAL_BALANCE,
        )
        print(
            f"Created paper trader id={trader['id']} name={trader['name']!r} "
            f"fingerprint={trader['strategy_fingerprint']} "
            f"symbol={trader['symbol']} exchange={trader['exchange']} "
            f"environment={trader['environment']} stake={trader['stake_amount']} "
            f"initial_balance={trader['initial_balance']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
