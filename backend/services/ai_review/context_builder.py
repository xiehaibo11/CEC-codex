"""Build review contexts from existing trading executor inputs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database.models import Account
from services.ai_review.schemas import ReviewContext


def build_review_context(
    *,
    account: Account,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    exchange: str,
    environment: str,
    trigger_context: Optional[Dict[str, Any]] = None,
    decision_kwargs: Optional[Dict[str, Any]] = None,
) -> ReviewContext:
    decision_kwargs = decision_kwargs or {}
    trigger_context = trigger_context or {}
    signal_trigger_id = trigger_context.get("signal_trigger_id") or decision_kwargs.get("signal_trigger_id")
    prompt_template_id = decision_kwargs.get("prompt_template_id")

    return ReviewContext(
        account_id=account.id,
        account_name=account.name,
        exchange=exchange,
        environment=environment,
        symbol=decision.get("symbol"),
        operation=decision.get("operation", "hold"),
        decision=decision,
        portfolio=portfolio,
        positions=positions or [],
        prices=prices or {},
        trigger_context=trigger_context,
        signal_trigger_id=signal_trigger_id,
        prompt_template_id=prompt_template_id,
    )
