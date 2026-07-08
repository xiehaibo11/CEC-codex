"""Loss-pattern and pre-trade risk reviewer for AI decisions."""
from __future__ import annotations

from sqlalchemy.orm import Session

from services.ai_review.schemas import AgentReview, AgentVerdict, ReviewContext
from services.trading_commands.risk_guards import check_pre_trade_guards


class LossReviewer:
    """Reuse deterministic loss-derived risk guards before opening exposure."""

    agent_role = "loss_reviewer"

    def review(self, db: Session, context: ReviewContext) -> AgentReview:
        if not context.is_opening_trade or not context.symbol:
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.PASS,
                confidence=1.0,
                report_text="非开仓动作不触发亏损复盘闸门。",
            )

        guard = check_pre_trade_guards(
            db,
            account_id=context.account_id,
            symbol=context.symbol,
            operation=context.operation,
            positions=context.positions,
            total_equity=_total_equity(context),
        )
        if not guard.get("allowed"):
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.BLOCK,
                confidence=1.0,
                blocking_reasons=[str(guard.get("reason") or "风控闸未通过")],
                evidence=[{"pre_trade_guard": guard}],
                report_text="亏损复盘提取出的硬风控阻止本次开仓。",
            )

        return AgentReview(
            agent_role=self.agent_role,
            verdict=AgentVerdict.PASS,
            confidence=0.95,
            evidence=[{"pre_trade_guard": guard}],
            report_text="未命中亏损复盘硬风控。",
        )


def _total_equity(context: ReviewContext) -> float:
    for key in ("total_assets", "total_equity", "equity", "account_value", "margin_balance"):
        value = context.portfolio.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0
