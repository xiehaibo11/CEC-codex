from sqlalchemy.exc import SQLAlchemyError

from services.ai_review.agents.execution_judge import ExecutionJudge
from services.ai_review.orchestrator import apply_final_review_to_decision, review_and_apply
from services.ai_review.schemas import AgentReview, AgentVerdict, FinalVerdict, ReviewAdjustment, ReviewContext


def _ctx():
    return ReviewContext(
        account_id=1,
        account_name="bot",
        exchange="binance",
        environment="mainnet",
        symbol="BTC",
        operation="buy",
        decision={"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 65000},
    )


def test_execution_judge_blocks_when_any_agent_blocks():
    final = ExecutionJudge().judge(
        _ctx(),
        [AgentReview("loss_reviewer", AgentVerdict.BLOCK, 0.9, blocking_reasons=["loss streak"])],
    )

    assert final.verdict == FinalVerdict.BLOCK
    assert final.blocking_reasons == ["loss streak"]


def test_execution_judge_reduces_to_smallest_reviewer_limit():
    final = ExecutionJudge().judge(
        _ctx(),
        [
            AgentReview("a", AgentVerdict.WARN, 0.7, recommended_adjustments=ReviewAdjustment(max_target_portion=0.2)),
            AgentReview("b", AgentVerdict.WARN, 0.7, recommended_adjustments=ReviewAdjustment(max_leverage=3)),
        ],
    )

    assert final.verdict == FinalVerdict.REDUCE_SIZE
    assert final.max_target_portion == 0.2
    assert final.max_leverage == 3


def test_apply_final_review_blocks_without_exchange_execution():
    decision = {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10}
    final = ExecutionJudge().judge(
        _ctx(),
        [AgentReview("loss_reviewer", AgentVerdict.BLOCK, 0.9, blocking_reasons=["loss streak"])],
    )

    result = apply_final_review_to_decision(decision, final)

    assert result["allowed"] is False
    assert decision["review_verdict"] == "block"
    assert decision["review_blocked_reason"] == "loss streak"
    assert decision["review_result"]["verdict"] == "block"


def test_apply_final_review_marks_legacy_risk_guard_block():
    decision = {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10}
    final = ExecutionJudge().judge(
        _ctx(),
        [AgentReview("loss_reviewer", AgentVerdict.BLOCK, 0.9, blocking_reasons=["风控闸：连续亏损"])],
    )

    result = apply_final_review_to_decision(decision, final)

    assert result["allowed"] is False
    assert decision["_risk_guard_blocked"] == "风控闸：连续亏损"


def test_apply_final_review_reduces_size_and_leverage():
    decision = {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10}
    final = ExecutionJudge().judge(
        _ctx(),
        [
            AgentReview(
                "risk",
                AgentVerdict.WARN,
                0.8,
                recommended_adjustments=ReviewAdjustment(max_target_portion=0.1, max_leverage=2),
            )
        ],
    )

    result = apply_final_review_to_decision(decision, final)

    assert result["allowed"] is True
    assert decision["target_portion_of_balance"] == 0.1
    assert decision["leverage"] == 2
    assert decision["review_verdict"] == "reduce_size"


def test_review_and_apply_blocks_when_persistence_fails(monkeypatch):
    class _Db:
        rolled_back = False

        def rollback(self):
            self.rolled_back = True

    decision = {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10}
    approved = ExecutionJudge().judge(_ctx(), [AgentReview("ok", AgentVerdict.PASS, 1.0)])

    monkeypatch.setattr("services.ai_review.orchestrator.run_review_pipeline", lambda *args: approved)
    monkeypatch.setattr(
        "services.ai_review.orchestrator.save_review_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(SQLAlchemyError("missing review table")),
    )

    db = _Db()
    result = review_and_apply(
        db,
        account=type("_Account", (), {"id": 1, "name": "bot"})(),
        decision=decision,
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 65000},
        exchange="binance",
        environment="paper",
    )

    assert result["allowed"] is False
    assert db.rolled_back is True
    assert decision["review_verdict"] == "block"
    assert "审查落库失败" in decision["review_blocked_reason"]
