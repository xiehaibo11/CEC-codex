"""Typed contracts for the AI review layer."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentVerdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    TESTNET_ONLY = "testnet_only"


class FinalVerdict(str, Enum):
    APPROVE = "approve"
    REDUCE_SIZE = "reduce_size"
    HOLD = "hold"
    BLOCK = "block"
    TESTNET_ONLY = "testnet_only"


@dataclass
class ReviewAdjustment:
    max_target_portion: Optional[float] = None
    max_leverage: Optional[int] = None

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "max_target_portion": self.max_target_portion,
            "max_leverage": self.max_leverage,
        }


@dataclass
class AgentReview:
    agent_role: str
    verdict: AgentVerdict
    confidence: float
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)
    recommended_adjustments: ReviewAdjustment = field(default_factory=ReviewAdjustment)
    report_text: str = ""

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "agent_role": self.agent_role,
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "warnings": self.warnings,
            "blocking_reasons": self.blocking_reasons,
            "recommended_adjustments": self.recommended_adjustments.to_snapshot(),
            "report_text": self.report_text,
        }


@dataclass
class ReviewContext:
    account_id: int
    account_name: str
    exchange: str
    environment: str
    symbol: Optional[str]
    operation: str
    decision: Dict[str, Any]
    portfolio: Dict[str, Any]
    positions: List[Dict[str, Any]]
    prices: Dict[str, float]
    trigger_context: Optional[Dict[str, Any]] = None
    signal_trigger_id: Optional[int] = None
    prompt_template_id: Optional[int] = None

    def __post_init__(self) -> None:
        self.exchange = (self.exchange or "hyperliquid").lower()
        self.environment = (self.environment or "paper").lower()
        self.symbol = self.symbol.upper() if self.symbol else None
        self.operation = (self.operation or "hold").lower()

    @property
    def is_opening_trade(self) -> bool:
        return self.operation in {"buy", "sell"}

    @property
    def is_risk_reducing(self) -> bool:
        return self.operation in {"close", "hold"}


@dataclass
class FinalReview:
    verdict: FinalVerdict
    symbol: Optional[str]
    operation: str
    max_target_portion: float
    max_leverage: int
    summary: str
    blocking_reasons: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    agent_reports: List[AgentReview] = field(default_factory=list)
    review_run_id: Optional[int] = None

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "symbol": self.symbol,
            "operation": self.operation,
            "max_target_portion": self.max_target_portion,
            "max_leverage": self.max_leverage,
            "summary": self.summary,
            "blocking_reasons": self.blocking_reasons,
            "required_evidence": self.required_evidence,
            "review_run_id": self.review_run_id,
            "agent_reports": [report.to_snapshot() for report in self.agent_reports],
        }


def clamp_final_review(
    review: FinalReview,
    *,
    original_target_portion: float,
    original_leverage: int,
) -> FinalReview:
    return replace(
        review,
        max_target_portion=min(review.max_target_portion, original_target_portion),
        max_leverage=min(review.max_leverage, original_leverage),
    )
