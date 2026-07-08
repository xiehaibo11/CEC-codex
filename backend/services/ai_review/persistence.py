"""Persistence helpers for AI review reports."""
from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from database.models.trading import AIReviewAgentReport, AIReviewRun
from services.ai_review.schemas import FinalReview, ReviewContext


def save_review_run(
    db: Session,
    context: ReviewContext,
    review: FinalReview,
    *,
    started_at: Optional[float] = None,
) -> FinalReview:
    latency_ms = None
    if started_at is not None:
        latency_ms = int((time.monotonic() - started_at) * 1000)

    run = AIReviewRun(
        account_id=context.account_id,
        exchange=context.exchange,
        environment=context.environment,
        symbol=context.symbol,
        operation=context.operation,
        original_target_portion=Decimal(str(context.decision.get("target_portion_of_balance") or 0)),
        original_leverage=int(context.decision.get("leverage") or 1),
        verdict=review.verdict.value,
        final_target_portion=Decimal(str(review.max_target_portion)),
        final_leverage=review.max_leverage,
        final_reason=review.summary,
        latency_ms=latency_ms,
    )
    db.add(run)
    db.flush()

    for report in review.agent_reports:
        db.add(
            AIReviewAgentReport(
                review_run_id=run.id,
                agent_role=report.agent_role,
                verdict=report.verdict.value,
                confidence=Decimal(str(report.confidence)),
                report_json=json.dumps(report.to_snapshot(), ensure_ascii=False),
                report_text=report.report_text,
            )
        )
    db.commit()
    review.review_run_id = run.id
    return review
