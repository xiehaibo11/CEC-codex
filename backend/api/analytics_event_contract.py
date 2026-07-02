"""Event-contract dimension of attribution analytics.

Reads settled `EventContractPaperBet` rows and builds the overview +
direction/market_state/hour-bucket breakdowns consumed by
`GET /api/analytics/event-contract` (and folded into `/api/analytics/summary`
`by_source.event_contract`). Kept out of `analytics_routes.py` so that file
stays a thin router shell.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import EventContractPaperBet
from services.event_contract.backtest_stats import wilson_interval

_SETTLED = "settled"

# Fixed, chronologically ordered UTC hour buckets (always emitted, even empty).
_HOUR_BUCKET_KEYS: List[str] = [f"h{start:02d}-{start + 3:02d}" for start in range(0, 24, 4)]


def _hour_bucket_key(hour: int) -> str:
    start = (hour // 4) * 4
    return f"h{start:02d}-{start + 3:02d}"


def _win_rate(wins: int, decided: int) -> float:
    return round(wins / decided * 100, 2) if decided else 0.0


def _query_settled_bets(
    db: Session,
    trader_id: Optional[int],
    start: Optional[datetime],
    end: Optional[datetime],
) -> List[EventContractPaperBet]:
    query = db.query(EventContractPaperBet).filter(EventContractPaperBet.status == _SETTLED)
    if trader_id is not None:
        query = query.filter(EventContractPaperBet.trader_id == trader_id)
    if start is not None:
        query = query.filter(EventContractPaperBet.decision_time >= start)
    if end is not None:
        query = query.filter(EventContractPaperBet.decision_time <= end)
    return query.all()


def _dimension_rows(groups: Dict[str, List[EventContractPaperBet]]) -> List[Dict[str, Any]]:
    rows = []
    for key in sorted(groups.keys()):
        bets = groups[key]
        wins = sum(1 for b in bets if b.result == "win")
        losses = sum(1 for b in bets if b.result == "loss")
        decided = wins + losses
        pnl = sum(float(b.pnl or 0) for b in bets)
        rows.append(
            {
                "key": key,
                "n": len(bets),
                "win_rate": _win_rate(wins, decided),
                "pnl": round(pnl, 2),
            }
        )
    return rows


def _hour_bucket_rows(groups: Dict[str, List[EventContractPaperBet]]) -> List[Dict[str, Any]]:
    rows = []
    for key in _HOUR_BUCKET_KEYS:
        bets = groups.get(key, [])
        wins = sum(1 for b in bets if b.result == "win")
        losses = sum(1 for b in bets if b.result == "loss")
        decided = wins + losses
        pnl = sum(float(b.pnl or 0) for b in bets)
        rows.append(
            {
                "key": key,
                "n": len(bets),
                "win_rate": _win_rate(wins, decided),
                "pnl": round(pnl, 2),
            }
        )
    return rows


def build_event_contract_attribution(
    db: Session,
    trader_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Attribution analytics for settled event-contract paper bets.

    Returns overview stats (Wilson CI on decided win-rate) plus
    direction / market_state / UTC-hour-bucket breakdowns.
    """
    settled = _query_settled_bets(db, trader_id, start, end)

    wins = sum(1 for b in settled if b.result == "win")
    losses = sum(1 for b in settled if b.result == "loss")
    draws = sum(1 for b in settled if b.result == "draw")
    decided = wins + losses
    ci_low, ci_high = wilson_interval(wins, decided)
    total_pnl = round(sum(float(b.pnl or 0) for b in settled), 2)

    by_direction: Dict[str, List[EventContractPaperBet]] = defaultdict(list)
    by_market_state: Dict[str, List[EventContractPaperBet]] = defaultdict(list)
    by_hour_bucket: Dict[str, List[EventContractPaperBet]] = defaultdict(list)

    for bet in settled:
        direction_key = bet.direction or "unknown"
        by_direction[direction_key].append(bet)

        state_key = bet.market_state or "unknown"
        by_market_state[state_key].append(bet)

        if bet.decision_time is not None:
            by_hour_bucket[_hour_bucket_key(bet.decision_time.hour)].append(bet)

    return {
        "overview": {
            "n": len(settled),
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "decided": decided,
            "decided_win_rate": _win_rate(wins, decided),
            "win_rate_ci_low": ci_low,
            "win_rate_ci_high": ci_high,
            "total_pnl": total_pnl,
        },
        "by_direction": _dimension_rows(by_direction),
        "by_market_state": _dimension_rows(by_market_state),
        "by_hour_bucket": _hour_bucket_rows(by_hour_bucket),
    }
