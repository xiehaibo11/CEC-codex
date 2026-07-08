"""Signal provenance reviewer for AI trading decisions."""
from __future__ import annotations

from sqlalchemy.orm import Session

from services.ai_review.schemas import AgentReview, AgentVerdict, ReviewContext
from services.signal_trigger_validation import signal_validation_gate


class SignalReviewer:
    """Check whether an opening decision is supported by a validated signal."""

    agent_role = "signal_reviewer"

    def review(self, db: Session, context: ReviewContext) -> AgentReview:
        if not context.is_opening_trade:
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.PASS,
                confidence=1.0,
                report_text="非开仓动作不需要信号闸门。",
            )

        trigger_context = context.trigger_context or {}
        trigger_type = trigger_context.get("trigger_type")
        if trigger_type != "signal":
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.WARN,
                confidence=0.9,
                warnings=["非信号触发的开仓只能作为低置信度候选，需由执行评委降级或限仓。"],
                evidence=[{"trigger_type": trigger_type or "unknown"}],
                report_text="缺少结构化信号来源。",
            )

        if context.environment == "mainnet":
            gate = signal_validation_gate(db, trigger_context)
            if not gate.get("allowed"):
                return AgentReview(
                    agent_role=self.agent_role,
                    verdict=AgentVerdict.BLOCK,
                    confidence=1.0,
                    blocking_reasons=[str(gate.get("reason") or "信号验证门未通过")],
                    evidence=[{"signal_validation_gate": gate}],
                    report_text="主网信号未通过前向验证。",
                )

        return AgentReview(
            agent_role=self.agent_role,
            verdict=AgentVerdict.PASS,
            confidence=0.95,
            evidence=[{"trigger_type": "signal", "environment": context.environment}],
            report_text="信号来源满足当前环境要求。",
        )
