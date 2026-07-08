"""Backtest evidence reviewer for signal-driven AI decisions."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from services.ai_review.schemas import AgentReview, AgentVerdict, ReviewContext


class BacktestReviewer:
    """Require explicit backtest evidence before promoting signal opens."""

    agent_role = "backtest_reviewer"

    def review(self, db: Session, context: ReviewContext) -> AgentReview:
        del db
        if not context.is_opening_trade:
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.PASS,
                confidence=1.0,
                report_text="非开仓动作不需要回测闸门。",
            )

        trigger_context = context.trigger_context or {}
        if trigger_context.get("trigger_type") != "signal":
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.PASS,
                confidence=0.8,
                report_text="非信号触发，回测审查不作为主闸门。",
            )

        summary = _summary(trigger_context)
        if not summary:
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.WARN,
                confidence=0.9,
                warnings=["缺少回测摘要，不能证明该信号在历史样本中有效。"],
                report_text="信号没有携带回测摘要。",
            )

        net_pnl = float(summary.get("net_pnl") or 0)
        if net_pnl < 0:
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.BLOCK,
                confidence=1.0,
                blocking_reasons=[f"回测净盈亏为负：{net_pnl}"],
                evidence=[{"backtest_summary": summary}],
                report_text="历史回测为负，不允许继续执行同类开仓。",
            )

        if summary.get("target_sample_met") is False:
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.TESTNET_ONLY,
                confidence=0.95,
                warnings=["回测/前向样本数未达标，只允许测试网或观察模式继续收集样本。"],
                evidence=[{"backtest_summary": summary}],
                report_text="样本不足，不能升级主网。",
            )

        slippage_bps = float(summary.get("slippage_bps") or 0)
        if slippage_bps <= 0:
            return AgentReview(
                agent_role=self.agent_role,
                verdict=AgentVerdict.WARN,
                confidence=0.85,
                warnings=["回测摘要缺少滑点成本，收益可能被高估。"],
                evidence=[{"backtest_summary": summary}],
                report_text="回测没有显式滑点假设。",
            )

        return AgentReview(
            agent_role=self.agent_role,
            verdict=AgentVerdict.PASS,
            confidence=0.95,
            evidence=[{"backtest_summary": summary}],
            report_text="回测摘要满足最低执行证据要求。",
        )


def _summary(trigger_context: Dict[str, Any]) -> Dict[str, Any]:
    raw = trigger_context.get("backtest_summary") or trigger_context.get("backtest") or {}
    return raw if isinstance(raw, dict) else {}
