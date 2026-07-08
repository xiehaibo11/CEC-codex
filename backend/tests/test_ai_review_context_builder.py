from services.ai_review.context_builder import build_review_context


class DummyAccount:
    id = 42
    name = "Decision Bot"


def test_build_review_context_extracts_decision_fields():
    ctx = build_review_context(
        account=DummyAccount(),
        decision={"operation": "sell", "symbol": "eth", "target_portion_of_balance": 0.4, "leverage": 8},
        portfolio={"total_assets": 5000},
        positions=[{"coin": "ETH", "szi": -0.2, "position_value": 800}],
        prices={"ETH": 3200},
        exchange="binance",
        environment="testnet",
        trigger_context={"trigger_type": "signal", "signal_trigger_id": 9},
        decision_kwargs={"prompt_template_id": 3},
    )

    assert ctx.account_id == 42
    assert ctx.account_name == "Decision Bot"
    assert ctx.exchange == "binance"
    assert ctx.environment == "testnet"
    assert ctx.symbol == "ETH"
    assert ctx.operation == "sell"
    assert ctx.signal_trigger_id == 9
    assert ctx.prompt_template_id == 3


def test_build_review_context_uses_decision_kwargs_signal_id_when_trigger_context_lacks_it():
    ctx = build_review_context(
        account=DummyAccount(),
        decision={"operation": "buy", "symbol": "btc"},
        portfolio={"total_assets": 5000},
        positions=[],
        prices={"BTC": 65000},
        exchange="hyperliquid",
        environment="mainnet",
        trigger_context={"trigger_type": "signal"},
        decision_kwargs={"signal_trigger_id": 77},
    )

    assert ctx.signal_trigger_id == 77
