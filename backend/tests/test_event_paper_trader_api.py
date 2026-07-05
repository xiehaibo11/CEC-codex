"""TDD coverage for the event-contract paper trader HTTP API service layer
(spec module 1): create/list/toggle/bets/stats, all against an in-memory
sqlite session. Route file is a thin shell (no TestClient needed per the
task brief)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models.event_contract import EventContractPaperBet, EventContractPaperTrader
from services.event_contract import paper_trader_api
from services.event_contract.backtest_stats import wilson_interval
from services.event_contract_service import event_contract_service


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[EventContractPaperTrader.__table__, EventContractPaperBet.__table__]
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _make_trader(db, **overrides):
    name = overrides.pop("name", "run-850-clone")
    config = overrides.pop("config", {"symbol": "BTC", "exchange": "binance"})
    stake_amount = overrides.pop("stake_amount", 100.0)
    initial_balance = overrides.pop("initial_balance", 10000.0)
    return paper_trader_api.create_paper_trader(
        db, name=name, config=config, stake_amount=stake_amount, initial_balance=initial_balance
    )


def _add_settled_bet(db, trader_id, result, pnl, stake=100.0, payout=0.8):
    bet = EventContractPaperBet(
        trader_id=trader_id,
        direction="long",
        status="settled",
        decision_time=__import__("datetime").datetime(2026, 7, 1, 0, 0, 0),
        stake=stake,
        payout_ratio=payout,
        result=result,
        pnl=pnl,
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


class TestCreatePaperTrader:
    def test_creates_trader_with_normalized_symbol_and_fingerprint(self, session):
        trader = _make_trader(session, config={"symbol": "btcusdt", "exchange": "Binance"})
        assert trader["symbol"] == "BTC"
        assert trader["exchange"] == "binance"
        assert trader["enabled"] is True
        assert trader["stake_amount"] == 100.0
        assert trader["initial_balance"] == 10000.0
        assert trader["current_balance"] == 10000.0
        assert trader["strategy_fingerprint"]

        cfg = event_contract_service._normalize_config(
            {"symbol": "btcusdt", "exchange": "Binance"}, prediction=True
        )
        expected_fingerprint = event_contract_service._strategy_fingerprint(cfg)
        assert trader["strategy_fingerprint"] == expected_fingerprint

    def test_invalid_config_raises_value_error(self, session):
        with pytest.raises(ValueError):
            paper_trader_api.create_paper_trader(
                session, name="bad", config={"period": "not_a_real_period"}
            )

    def test_duplicate_name_rejected(self, session):
        _make_trader(session, name="dup")
        with pytest.raises(ValueError):
            _make_trader(session, name="dup")

    def test_missing_name_rejected(self, session):
        with pytest.raises(ValueError):
            paper_trader_api.create_paper_trader(session, name="  ", config={})


class TestListAndToggle:
    def test_list_includes_inline_stats_shape(self, session):
        trader = _make_trader(session)
        listed = paper_trader_api.list_paper_traders(session)
        assert len(listed) == 1
        item = listed[0]
        for key in (
            "trader_id", "n_settled", "decided", "wins", "losses", "draws",
            "decided_win_rate", "win_rate_ci_low", "win_rate_ci_high",
            "p_value_vs_breakeven", "break_even_win_rate", "total_pnl",
            "current_balance", "stake_amount", "open_bets", "strategy_fingerprint",
        ):
            assert key in item, f"missing stats key {key}"
        assert item["trader_id"] == trader["id"]
        assert item["n_settled"] == 0
        # Cost floor enforces min 0.1% fee: break_even = (1 + 0.001) / (1 + 0.8) * 100 ≈ 55.61
        assert item["break_even_win_rate"] == pytest.approx(55.61, abs=0.01)
        assert item["p_value_vs_breakeven"] == 1.0

    def test_toggle_enabled(self, session):
        trader = _make_trader(session)
        assert trader["enabled"] is True
        updated = paper_trader_api.set_paper_trader_enabled(session, trader["id"], False)
        assert updated["enabled"] is False
        again = paper_trader_api.set_paper_trader_enabled(session, trader["id"], True)
        assert again["enabled"] is True

    def test_toggle_missing_trader_raises(self, session):
        with pytest.raises(ValueError):
            paper_trader_api.set_paper_trader_enabled(session, 9999, True)


class TestStatsMath:
    def test_known_wins_losses_stats(self, session):
        trader = _make_trader(session)
        trader_id = trader["id"]
        for _ in range(3):
            _add_settled_bet(session, trader_id, "win", 80.0)
        for _ in range(2):
            _add_settled_bet(session, trader_id, "loss", -100.0)

        stats = paper_trader_api.get_paper_trader_stats(session, trader_id)

        assert stats["trader_id"] == trader_id
        assert stats["n_settled"] == 5
        assert stats["decided"] == 5
        assert stats["wins"] == 3
        assert stats["losses"] == 2
        assert stats["draws"] == 0
        assert stats["decided_win_rate"] == pytest.approx(60.0)

        expected_lo, expected_hi = wilson_interval(3, 5)
        assert stats["win_rate_ci_low"] == expected_lo
        assert stats["win_rate_ci_high"] == expected_hi

        # Cost floor enforces min 0.1% fee: break_even = (1 + 0.001) / (1 + 0.8) * 100 ≈ 55.61
        # break-even for the default payout=0.8/fee_rate floored to 0.001: (1.001)/(1.8)*100
        assert stats["break_even_win_rate"] == pytest.approx(55.61, abs=0.01)
        assert stats["total_pnl"] == pytest.approx(3 * 80 - 2 * 100)  # +40
        assert stats["current_balance"] == 10000.0  # only bet.pnl updates balance in the live cycle
        assert stats["stake_amount"] == 100.0
        assert stats["open_bets"] == 0
        assert stats["strategy_fingerprint"] == trader["strategy_fingerprint"]

    def test_open_and_pending_bets_counted_separately_from_settled(self, session):
        trader = _make_trader(session)
        trader_id = trader["id"]
        _add_settled_bet(session, trader_id, "win", 80.0)
        session.add(
            EventContractPaperBet(
                trader_id=trader_id,
                direction="short",
                status="pending_entry",
                decision_time=__import__("datetime").datetime(2026, 7, 1, 0, 5, 0),
                stake=100.0,
                payout_ratio=0.8,
            )
        )
        session.add(
            EventContractPaperBet(
                trader_id=trader_id,
                direction="long",
                status="open",
                decision_time=__import__("datetime").datetime(2026, 7, 1, 0, 10, 0),
                stake=100.0,
                payout_ratio=0.8,
            )
        )
        session.commit()

        stats = paper_trader_api.get_paper_trader_stats(session, trader_id)
        assert stats["n_settled"] == 1
        assert stats["open_bets"] == 2

    def test_stats_missing_trader_raises(self, session):
        with pytest.raises(ValueError):
            paper_trader_api.get_paper_trader_stats(session, 9999)


class TestBetsPagination:
    def test_newest_first_and_total_count(self, session):
        import datetime

        trader = _make_trader(session)
        trader_id = trader["id"]
        for i in range(5):
            session.add(
                EventContractPaperBet(
                    trader_id=trader_id,
                    direction="long",
                    status="settled",
                    decision_time=datetime.datetime(2026, 7, 1, 0, i, 0),
                    stake=100.0,
                    payout_ratio=0.8,
                    result="win",
                    pnl=80.0,
                )
            )
        session.commit()

        page = paper_trader_api.get_paper_trader_bets(session, trader_id, limit=2, offset=0)
        assert page["total"] == 5
        assert page["limit"] == 2
        assert page["offset"] == 0
        assert len(page["bets"]) == 2
        # newest decision_time first
        assert page["bets"][0]["decision_time"] > page["bets"][1]["decision_time"]
        assert page["bets"][0]["decision_time"] == "2026-07-01T00:04:00"

        page2 = paper_trader_api.get_paper_trader_bets(session, trader_id, limit=2, offset=2)
        assert len(page2["bets"]) == 2
        assert page2["bets"][0]["decision_time"] == "2026-07-01T00:02:00"

        page3 = paper_trader_api.get_paper_trader_bets(session, trader_id, limit=2, offset=4)
        assert len(page3["bets"]) == 1
        assert page3["bets"][0]["decision_time"] == "2026-07-01T00:00:00"

    def test_bets_missing_trader_raises(self, session):
        with pytest.raises(ValueError):
            paper_trader_api.get_paper_trader_bets(session, 9999)
