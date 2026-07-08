"""Run AI decision reviews and apply final verdicts."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.ai_review.agents import BacktestReviewer, LossReviewer, SignalReviewer
from services.ai_review.agents.execution_judge import ExecutionJudge
from services.ai_review.context_builder import build_review_context
from services.ai_review.persistence import save_review_run
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
    if decision["review_blocked_reason"]:
        decision["_ai_review_blocked"] = decision["review_blocked_reason"]
        if "风控闸" in decision["review_blocked_reason"]:
            decision["_risk_guard_blocked"] = decision["review_blocked_reason"]

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


def review_and_apply(
    db: Session,
    *,
    account,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    exchange: str,
    environment: str,
    trigger_context=None,
    decision_kwargs=None,
) -> Dict[str, Any]:
    if (decision.get("operation") or "").lower() in {"close", "hold"}:
        return {"allowed": True, "review": None, "reason": "risk-reducing operation"}

    started_at = time.monotonic()
    context = build_review_context(
        account=account,
        decision=decision,
        portfolio=portfolio,
        positions=positions,
        prices=prices,
        exchange=exchange,
        environment=environment,
        trigger_context=trigger_context,
        decision_kwargs=decision_kwargs,
    )
    review = run_review_pipeline(db, context)
    try:
        review = save_review_run(db, context, review, started_at=started_at)
    except SQLAlchemyError as err:
        rollback = getattr(db, "rollback", None)
        if callable(rollback):
            rollback()
        decision["_ai_review_persistence_error"] = str(err)
        if review.verdict not in {FinalVerdict.BLOCK, FinalVerdict.HOLD}:
            review = FinalReview(
                verdict=FinalVerdict.BLOCK,
                symbol=context.symbol,
                operation=context.operation,
                max_target_portion=0,
                max_leverage=1,
                summary="AI审查落库失败，安全阻断。",
                blocking_reasons=[f"AI审查落库失败：{err}"],
                agent_reports=review.agent_reports,
            )
    applied = apply_final_review_to_decision(decision, review)
    return {"allowed": applied["allowed"], "review": review, "reason": applied["reason"]}
