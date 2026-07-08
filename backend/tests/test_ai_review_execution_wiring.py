import pytest

from services.ai_review.schemas import FinalReview, FinalVerdict


class _ExplodingClient:
    def place_order_with_tpsl(self, *args, **kwargs):
        raise AssertionError("exchange client must not be called after review block")


class _Account:
    id = 1
    name = "reviewed"
    model = "test-model"
    default_leverage = 3


class _Wallet:
    environment = "testnet"
    rebate_working = True


@pytest.fixture()
def session():
    return object()


def _blocked_review():
    return FinalReview(
        verdict=FinalVerdict.BLOCK,
        symbol="BTC",
        operation="buy",
        max_target_portion=0,
        max_leverage=1,
        summary="blocked by review",
        blocking_reasons=["blocked by review"],
    )


def test_binance_review_block_saves_without_exchange_call(session, monkeypatch):
    from services.trading_commands import binance_execution

    saved = []
    monkeypatch.setattr(
        binance_execution,
        "save_ai_decision",
        lambda *args, **kwargs: saved.append({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        "services.ai_review.orchestrator.review_and_apply",
        lambda *args, **kwargs: {"allowed": False, "review": _blocked_review(), "reason": "blocked by review"},
    )

    binance_execution._execute_binance_decision(
        session,
        _Account(),
        _ExplodingClient(),
        {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.2, "leverage": 3},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 65000},
        available_balance=900,
        decision_kwargs={},
        wallet=_Wallet(),
    )

    assert len(saved) == 1
    assert saved[0]["kwargs"]["executed"] is False


def test_hyperliquid_review_block_saves_without_entry_order(session, monkeypatch):
    from services.trading_commands import hyperliquid_execution

    saved = []
    reviews = []

    def fake_review_and_apply(*args, **kwargs):
        reviews.append(kwargs)
        return {"allowed": False, "review": _blocked_review(), "reason": "blocked by review"}

    monkeypatch.setattr(
        hyperliquid_execution,
        "save_ai_decision",
        lambda *args, **kwargs: saved.append({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        "services.ai_review.orchestrator.review_and_apply",
        fake_review_and_apply,
    )
    monkeypatch.setattr(
        "services.hyperliquid_environment.get_leverage_settings",
        lambda *args, **kwargs: {"max_leverage": 20, "default_leverage": 3},
    )
    monkeypatch.setattr(
        hyperliquid_execution,
        "_execute_entry_order",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("entry order blocked")),
    )

    hyperliquid_execution._execute_hyperliquid_decision(
        db=session,
        account=_Account(),
        client=object(),
        decision={"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.2, "leverage": 3},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 65000},
        available_balance=900,
        environment="testnet",
        wallet_address="0xtest",
        symbol_whitelist={"BTC"},
        decision_kwargs={},
        trigger_context={"trigger_type": "signal"},
    )

    assert len(saved) == 1
    assert saved[0]["kwargs"]["executed"] is False
    assert reviews[0]["trigger_context"] == {"trigger_type": "signal"}
