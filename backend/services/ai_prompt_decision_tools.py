"""Decision-history tools for AI Prompt generation."""

import json
import logging
from typing import List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def execute_get_decision_list(db: Session, trader_id: int, limit: int = 10) -> str:
    """Get recent AI decision history summary."""
    from database.models import AIDecisionLog

    try:
        limit = min(max(limit, 1), 20)
        total_count = db.query(AIDecisionLog).filter(
            AIDecisionLog.account_id == trader_id
        ).count()
        decisions = db.query(AIDecisionLog).filter(
            AIDecisionLog.account_id == trader_id
        ).order_by(AIDecisionLog.decision_time.desc()).limit(limit).all()

        result = {
            "trader_id": trader_id,
            "decisions": [],
            "total": total_count,
            "showing": len(decisions),
        }

        for decision in decisions:
            trigger = f"signal:{decision.signal_trigger_id}" if decision.signal_trigger_id else "scheduled"
            decision_info = {
                "id": decision.id,
                "time": (
                    decision.decision_time.strftime("%Y-%m-%d %H:%M UTC")
                    if decision.decision_time else None
                ),
                "trigger": trigger,
                "symbol": decision.symbol,
                "operation": decision.operation,
                "target_portion": (
                    float(decision.target_portion) if decision.target_portion else None
                ),
                "executed": decision.executed,
                "exchange": decision.exchange or "hyperliquid",
                "has_prompt": bool(decision.prompt_snapshot),
                "has_reasoning": bool(decision.reasoning_snapshot),
            }
            if decision.realized_pnl is not None:
                decision_info["realized_pnl"] = float(decision.realized_pnl)
            result["decisions"].append(decision_info)

        if total_count == 0:
            result["note"] = "No decisions found for this trader."
        else:
            result["note"] = (
                f"Showing {len(decisions)} of {total_count} decisions. "
                "Use get_decision_details to see prompt/reasoning."
            )

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as exc:
        logger.error(f"[get_decision_list] Error: {exc}")
        return json.dumps({"error": str(exc)})


def execute_get_decision_details(
    db: Session,
    decision_ids: List[int],
    fields: List[str] = None,
) -> str:
    """Get detailed info for specific decisions."""
    from database.models import AIDecisionLog

    try:
        if fields is None:
            fields = ["summary"]

        decision_ids = decision_ids[:5]
        if not decision_ids:
            return json.dumps({"error": "No decision_ids provided"})

        decisions = db.query(AIDecisionLog).filter(
            AIDecisionLog.id.in_(decision_ids)
        ).all()

        if not decisions:
            return json.dumps({"error": f"No decisions found for ids: {decision_ids}"})

        result = {"decisions": []}
        for decision in decisions:
            item = {"id": decision.id}

            if "summary" in fields:
                trigger = (
                    f"signal:{decision.signal_trigger_id}"
                    if decision.signal_trigger_id else "scheduled"
                )
                item["summary"] = {
                    "time": (
                        decision.decision_time.strftime("%Y-%m-%d %H:%M UTC")
                        if decision.decision_time else None
                    ),
                    "trigger": trigger,
                    "symbol": decision.symbol,
                    "operation": decision.operation,
                    "target_portion": (
                        float(decision.target_portion) if decision.target_portion else None
                    ),
                    "executed": decision.executed,
                    "exchange": decision.exchange or "hyperliquid",
                }

                if decision.realized_pnl is not None:
                    item["summary"]["realized_pnl"] = float(decision.realized_pnl)

            if "prompt" in fields:
                item["prompt"] = decision.prompt_snapshot if decision.prompt_snapshot else None
                if not decision.prompt_snapshot:
                    item["prompt_note"] = "No prompt snapshot available for this decision"

            if "reasoning" in fields:
                item["reasoning"] = decision.reasoning_snapshot if decision.reasoning_snapshot else None
                if not decision.reasoning_snapshot:
                    item["reasoning_note"] = "No reasoning snapshot available for this decision"

            if "decision" in fields:
                if decision.decision_snapshot:
                    try:
                        item["decision"] = (
                            json.loads(decision.decision_snapshot)
                            if isinstance(decision.decision_snapshot, str)
                            else decision.decision_snapshot
                        )
                    except json.JSONDecodeError:
                        item["decision"] = decision.decision_snapshot
                else:
                    item["decision"] = None
                    item["decision_note"] = "No decision snapshot available"

            result["decisions"].append(item)

        result["fields_requested"] = fields
        result["count"] = len(result["decisions"])
        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as exc:
        logger.error(f"[get_decision_details] Error: {exc}")
        return json.dumps({"error": str(exc)})
