"""Run AI decision reviews and apply final verdicts."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from services.ai_review.agents import BacktestReviewer, LossReviewer, SignalReviewer
from services.ai_review.agents.execution_judge import ExecutionJudge
from services.ai_review.schemas import FinalReview, FinalVerdict, ReviewContext


def run_review_pipeline(db: Session, context: ReviewContext) -> FinalReview:
    reports = [
        SignalReviewer().review(db, context),
        BacktestReviewer().review(db, context),
        LossReviewer().review(db, context),
    ]
    return ExecutionJudge().judge(context, reports)


def apply_final_review_to_decision(decision: Dict[str, Any], review: FinalReview) -> Dict[str, Any]:
    decision["review_result"] = review.to_snapshot()
    decision["review_verdict"] = review.verdict.value
    decision["review_blocked_reason"] = "; ".join(review.blocking_reasons) if review.blocking_reasons else None

    if review.review_run_id is not None:
        decision["review_run_id"] = review.review_run_id

    if review.verdict in {FinalVerdict.BLOCK, FinalVerdict.HOLD}:
        return {"allowed": False, "reason": decision.get("review_blocked_reason") or review.summary}

    if review.verdict == FinalVerdict.REDUCE_SIZE:
        if "target_portion_of_balance" in decision:
            decision["target_portion_of_balance"] = min(
                float(decision.get("target_portion_of_balance") or 0),
                review.max_target_portion,
            )
        if "leverage" in decision:
            decision["leverage"] = min(int(decision.get("leverage") or 1), review.max_leverage)

    return {"allowed": True, "reason": review.summary}
