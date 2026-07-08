"""Read-only APIs for AI review runs."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models.trading import AIReviewAgentReport, AIReviewRun

router = APIRouter(prefix="/api/ai-review", tags=["AI Review"])


def _run_to_dict(run: AIReviewRun) -> dict:
    return {
        "id": run.id,
        "account_id": run.account_id,
        "decision_log_id": run.decision_log_id,
        "exchange": run.exchange,
        "environment": run.environment,
        "symbol": run.symbol,
        "operation": run.operation,
        "verdict": run.verdict,
        "final_reason": run.final_reason,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/runs")
def list_review_runs(
    account_id: Optional[int] = Query(None),
    verdict: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(AIReviewRun).order_by(AIReviewRun.created_at.desc())
    if account_id is not None:
        query = query.filter(AIReviewRun.account_id == account_id)
    if verdict:
        query = query.filter(AIReviewRun.verdict == verdict)
    return {"items": [_run_to_dict(run) for run in query.limit(limit).all()]}


@router.get("/runs/{run_id}")
def get_review_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AIReviewRun).filter(AIReviewRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Review run not found")
    reports = (
        db.query(AIReviewAgentReport)
        .filter(AIReviewAgentReport.review_run_id == run_id)
        .order_by(AIReviewAgentReport.id.asc())
        .all()
    )
    data = _run_to_dict(run)
    data["agent_reports"] = [
        {
            "agent_role": report.agent_role,
            "verdict": report.verdict,
            "confidence": float(report.confidence) if report.confidence is not None else None,
            "report": json.loads(report.report_json) if report.report_json else None,
            "report_text": report.report_text,
        }
        for report in reports
    ]
    return data
