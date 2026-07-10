"""Hard time-based exit: AI positions close when their hold time is up.

用户规则（2026-07-10）：5分钟一到就平仓。The LLM decision loop runs on a
multi-minute cadence and cannot be trusted with sub-cycle exits, so a
deterministic 30s scheduler job closes any position held >= the limit.
Positions whose age cannot be established are SKIPPED with a warning —
closing a position blind could kill one opened seconds ago.
"""
from __future__ import annotations

from services.position_time_exit import (
    DEFAULT_MAX_HOLD_MINUTES,
    close_due_positions,
    positions_due_for_exit,
)


def _pos(coin="BTC", holding_seconds=None, szi=0.05):
    return {"coin": coin, "szi": szi, "holding_duration_seconds": holding_seconds}


class TestDueSelection:
    def test_position_over_limit_is_due(self):
        due, skipped = positions_due_for_exit([_pos(holding_seconds=301)], 300)
        assert [p["coin"] for p in due] == ["BTC"]
        assert skipped == []

    def test_position_under_limit_not_due(self):
        due, skipped = positions_due_for_exit([_pos(holding_seconds=120)], 300)
        assert due == [] and skipped == []

    def test_exactly_at_limit_is_due(self):
        due, _ = positions_due_for_exit([_pos(holding_seconds=300)], 300)
        assert len(due) == 1

    def test_unknown_age_skipped_never_closed(self):
        due, skipped = positions_due_for_exit([_pos(holding_seconds=None)], 300)
        assert due == []
        assert [p["coin"] for p in skipped] == ["BTC"]

    def test_default_limit_is_five_minutes(self):
        assert DEFAULT_MAX_HOLD_MINUTES == 5


class TestCloseExecution:
    class _FakeClient:
        def __init__(self, fail_on=None):
            self.closed = []
            self.fail_on = fail_on or set()

        def close_position(self, symbol, cancel_tpsl=True):
            if symbol in self.fail_on:
                raise RuntimeError("venue error")
            self.closed.append((symbol, cancel_tpsl))
            return {"order_id": f"oid-{symbol}", "status": "filled"}

    def test_closes_each_due_position_with_tpsl_cleanup(self):
        client = self._FakeClient()
        results = close_due_positions(
            client, [_pos("BTC", 400), _pos("ETH", 500)], max_hold_seconds=300
        )
        assert client.closed == [("BTC", True), ("ETH", True)]
        assert [r["symbol"] for r in results] == ["BTC", "ETH"]
        assert all(r["closed"] for r in results)

    def test_one_failure_does_not_stop_others(self):
        client = self._FakeClient(fail_on={"BTC"})
        results = close_due_positions(
            client, [_pos("BTC", 400), _pos("ETH", 500)], max_hold_seconds=300
        )
        assert ("ETH", True) in client.closed
        by_symbol = {r["symbol"]: r for r in results}
        assert by_symbol["BTC"]["closed"] is False
        assert by_symbol["ETH"]["closed"] is True

    def test_nothing_due_makes_no_calls(self):
        client = self._FakeClient()
        results = close_due_positions(client, [_pos("BTC", 60)], max_hold_seconds=300)
        assert client.closed == [] and results == []
