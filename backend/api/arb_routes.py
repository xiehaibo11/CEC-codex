"""Read-only API routes for the price-locked arbitrage opportunity detector.

Detector-only MVP: exposes the persistent opportunity log and its KPI summary
(lock accuracy, daily counts). There is no venue quote data anywhere in these
responses - the venue quote leg is a documented TODO in
services/arb_opportunity_detector.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models.arb import ArbOpportunityLog
from services.arb_opportunity_detector import (
    serialize_opportunity,
    summarize_opportunities,
)

router = APIRouter(prefix="/api/arb", tags=["arb"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/opportunities")
def list_opportunities(
    limit: int = Query(default=100, ge=1, le=1000),
    outcome: str | None = Query(default=None, pattern="^(pending|win|loss)$"),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(ArbOpportunityLog)
        if outcome:
            query = query.filter(ArbOpportunityLog.outcome == outcome)
        rows = query.order_by(ArbOpportunityLog.locked_at.desc()).limit(limit).all()
        return {"items": [serialize_opportunity(row) for row in rows]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    try:
        return summarize_opportunities(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
