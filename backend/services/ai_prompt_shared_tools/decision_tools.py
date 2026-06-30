"""
AI Prompt Shared Tools - AI decision history tools

Provides:
- get_decision_list: recent decision summaries.
- get_decision_details: full prompt/reasoning/decision content for IDs.
"""

import json
import logging
from typing import List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def execute_get_decision_list(db: Session, trader_id: int, limit: int = 10) -> str:
    """
    Get recent AI decision history (summary only).

    Args:
        db: Database session
        trader_id: AI Trader ID (account_id)
        limit: Max number of decisions to return (default: 10, max: 20)

    Returns:
        JSON string with decision summaries
    """
    from database.models import AIDecisionLog

    try:
        # Limit to reasonable range
        limit = min(max(limit, 1), 20)

        # Get total count
        total_count = db.query(AIDecisionLog).filter(
            AIDecisionLog.account_id == trader_id
        ).count()

        # Get recent decisions
        decisions = db.query(AIDecisionLog).filter(
            AIDecisionLog.account_id == trader_id
        ).order_by(AIDecisionLog.decision_time.desc()).limit(limit).all()

        result = {
            "trader_id": trader_id,
            "decisions": [],
            "total": total_count,
            "showing": len(decisions)
        }

        for d in decisions:
            # Determine trigger type
            if d.signal_trigger_id:
                trigger = f"signal:{d.signal_trigger_id}"
            else:
                trigger = "scheduled"

            decision_info = {
                "id": d.id,
                "time": d.decision_time.strftime("%Y-%m-%d %H:%M UTC") if d.decision_time else None,
                "trigger": trigger,
                "symbol": d.symbol,
                "operation": d.operation,
                "target_portion": float(d.target_portion) if d.target_portion else None,
                "executed": d.executed,
                "exchange": d.exchange or "hyperliquid",
                "has_prompt": bool(d.prompt_snapshot),
                "has_reasoning": bool(d.reasoning_snapshot)
            }

            # Add PnL if available
            if d.realized_pnl is not None:
                decision_info["realized_pnl"] = float(d.realized_pnl)

            result["decisions"].append(decision_info)

        if total_count == 0:
            result["note"] = "No decisions found for this trader."
        else:
            result["note"] = f"Showing {len(decisions)} of {total_count} decisions. Use get_decision_details to see prompt/reasoning."

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[get_decision_list] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_decision_details(db: Session, decision_ids: List[int], fields: List[str] = None) -> str:
    """
    Get detailed info for specific decisions.

    Args:
        db: Database session
        decision_ids: List of decision IDs to get details for (max 5)
        fields: Fields to include: summary, prompt, reasoning, decision

    Returns:
        JSON string with decision details
    """
    from database.models import AIDecisionLog

    try:
        if fields is None:
            fields = ["summary"]

        # Limit to 5 decisions
        decision_ids = decision_ids[:5]

        if not decision_ids:
            return json.dumps({"error": "No decision_ids provided"})

        # Get decisions
        decisions = db.query(AIDecisionLog).filter(
            AIDecisionLog.id.in_(decision_ids)
        ).all()

        if not decisions:
            return json.dumps({"error": f"No decisions found for ids: {decision_ids}"})

        result = {"decisions": []}

        for d in decisions:
            item = {"id": d.id}

            # Summary (always included if requested or as default)
            if "summary" in fields:
                # Determine trigger type
                if d.signal_trigger_id:
                    trigger = f"signal:{d.signal_trigger_id}"
                else:
                    trigger = "scheduled"

                item["summary"] = {
                    "time": d.decision_time.strftime("%Y-%m-%d %H:%M UTC") if d.decision_time else None,
                    "trigger": trigger,
                    "symbol": d.symbol,
                    "operation": d.operation,
                    "target_portion": float(d.target_portion) if d.target_portion else None,
                    "executed": d.executed,
                    "exchange": d.exchange or "hyperliquid"
                }

                if d.realized_pnl is not None:
                    item["summary"]["realized_pnl"] = float(d.realized_pnl)

            # Prompt snapshot
            if "prompt" in fields:
                if d.prompt_snapshot:
                    item["prompt"] = d.prompt_snapshot
                else:
                    item["prompt"] = None
                    item["prompt_note"] = "No prompt snapshot available for this decision"

            # Reasoning snapshot
            if "reasoning" in fields:
                if d.reasoning_snapshot:
                    item["reasoning"] = d.reasoning_snapshot
                else:
                    item["reasoning"] = None
                    item["reasoning_note"] = "No reasoning snapshot available for this decision"

            # Decision output
            if "decision" in fields:
                if d.decision_snapshot:
                    try:
                        if isinstance(d.decision_snapshot, str):
                            item["decision"] = json.loads(d.decision_snapshot)
                        else:
                            item["decision"] = d.decision_snapshot
                    except json.JSONDecodeError:
                        item["decision"] = d.decision_snapshot
                else:
                    item["decision"] = None
                    item["decision_note"] = "No decision snapshot available"

            result["decisions"].append(item)

        result["fields_requested"] = fields
        result["count"] = len(result["decisions"])

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[get_decision_details] Error: {e}")
        return json.dumps({"error": str(e)})
