from services.ai_review.schemas import (
    AgentReview,
    AgentVerdict,
    FinalReview,
    FinalVerdict,
    ReviewAdjustment,
    ReviewContext,
    clamp_final_review,
)


def test_review_context_normalizes_operation_and_environment():
    ctx = ReviewContext(
        account_id=7,
        account_name="review-bot",
        exchange="binance",
        environment="MAINNET",
        symbol="btc",
        operation="BUY",
        decision={"operation": "BUY", "symbol": "btc"},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 64000},
    )

    assert ctx.environment == "mainnet"
    assert ctx.symbol == "BTC"
    assert ctx.operation == "buy"
    assert ctx.is_opening_trade is True


def test_clamp_final_review_never_expands_risk():
    review = FinalReview(
        verdict=FinalVerdict.REDUCE_SIZE,
        symbol="BTC",
        operation="buy",
        max_target_portion=0.8,
        max_leverage=20,
        summary="judge tried to expand risk",
    )

    clamped = clamp_final_review(
        review,
        original_target_portion=0.25,
        original_leverage=5,
    )

    assert clamped.max_target_portion == 0.25
    assert clamped.max_leverage == 5


def test_agent_review_snapshot_is_json_ready():
    report = AgentReview(
        agent_role="signal_reviewer",
        verdict=AgentVerdict.BLOCK,
        confidence=0.9,
        evidence=[{"kind": "signal", "summary": "net pnl negative"}],
        blocking_reasons=["signal is not profitable"],
        report_text="Signal failed validation",
    )

    snapshot = report.to_snapshot()

    assert snapshot["agent_role"] == "signal_reviewer"
    assert snapshot["verdict"] == "block"
    assert snapshot["blocking_reasons"] == ["signal is not profitable"]
