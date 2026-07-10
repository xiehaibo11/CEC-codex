"""ORM models for the price-locked delayed-settlement arbitrage detector.

MVP scope: a persistent opportunity log only. Each row records the moment a
rolling hypothetical 5-minute event-contract window became "price-locked"
(price continuously on one side of the strike for the sustained-time threshold
AND beyond the minimum distance), and is settled in place at window expiry so
lock accuracy and daily opportunity counts can be measured. Venue quotes are
intentionally absent (no venue quote API exists in the stack yet).
"""
from sqlalchemy import Column, Float, Integer, String, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func

from ..connection import Base


class ArbOpportunityLog(Base):
    """One row per locked hypothetical event-contract window."""
    __tablename__ = "arb_opportunity_log"
    __table_args__ = (
        UniqueConstraint("symbol", "window_start", name="uq_arb_opportunity_symbol_window"),
    )

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    window_start = Column(TIMESTAMP, nullable=False)
    strike = Column(Float, nullable=False)
    direction = Column(String(8), nullable=False)  # above|below
    locked_at = Column(TIMESTAMP, nullable=False, index=True)
    remaining_seconds = Column(Integer, nullable=False)
    distance_pct = Column(Float, nullable=False)  # percent, e.g. 0.05 == 0.05%
    final_price = Column(Float, nullable=True)
    outcome = Column(String(8), nullable=False, default="pending", index=True)  # pending|win|loss
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
