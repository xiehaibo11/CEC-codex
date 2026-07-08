"""Final execution judge for AI review reports."""
from __future__ import annotations

from typing import List

from services.ai_review.schemas import AgentReview, AgentVerdict, FinalReview, FinalVerdict, ReviewContext


class ExecutionJudge:
    """Merge reviewer reports into one exchange-execution verdict."""

    def judge(self, context: ReviewContext, reports: List[AgentReview]) -> FinalReview:
        original_portion = float(context.decision.get("target_portion_of_balance") or 0)
        original_leverage = int(context.decision.get("leverage") or 1)
        blocking_reasons = [reason for report in reports for reason in report.blocking_reasons]

        if any(report.verdict == AgentVerdict.BLOCK for report in reports):
            return FinalReview(
                verdict=FinalVerdict.BLOCK,
                symbol=context.symbol,
                operation=context.operation,
                max_target_portion=0,
                max_leverage=1,
                summary="审查层阻断新增风险。",
                blocking_reasons=blocking_reasons,
                agent_reports=reports,
            )

        if context.environment == "mainnet" and any(report.verdict == AgentVerdict.TESTNET_ONLY for report in reports):
            return FinalReview(
                verdict=FinalVerdict.BLOCK,
                symbol=context.symbol,
                operation=context.operation,
                max_target_portion=0,
                max_leverage=1,
                summary="该决策仅允许测试网观察，主网阻断。",
                blocking_reasons=["review verdict is testnet_only on mainnet"],
                required_evidence=["forward_validation_record"],
                agent_reports=reports,
            )

        max_portion = original_portion
        max_leverage = original_leverage
        for report in reports:
            adjustment = report.recommended_adjustments
            if adjustment.max_target_portion is not None:
                max_portion = min(max_portion, adjustment.max_target_portion)
            if adjustment.max_leverage is not None:
                max_leverage = min(max_leverage, adjustment.max_leverage)

        if (
            max_portion < original_portion
            or max_leverage < original_leverage
            or any(report.verdict == AgentVerdict.WARN for report in reports)
        ):
            return FinalReview(
                verdict=FinalVerdict.REDUCE_SIZE,
                symbol=context.symbol,
                operation=context.operation,
                max_target_portion=max_portion,
                max_leverage=max_leverage,
                summary="审查通过但存在风险提示，限制仓位或杠杆。",
                agent_reports=reports,
            )

        return FinalReview(
            verdict=FinalVerdict.APPROVE,
            symbol=context.symbol,
            operation=context.operation,
            max_target_portion=max_portion,
            max_leverage=max_leverage,
            summary="审查通过，未发现阻断条件。",
            agent_reports=reports,
        )
