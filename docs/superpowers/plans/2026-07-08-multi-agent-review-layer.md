# Multi-Agent Review Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TradingAgents-inspired review layer that evaluates AI Trader decisions before exchange execution and can approve, reduce, hold, block, or mark orders as testnet-only.

**Architecture:** Add a lightweight `services.ai_review` orchestrator around deterministic reviewers first, preserving the existing AI decision engine and existing exchange risk guards. The review layer writes structured review results, never expands risk, and is invoked before Binance and Hyperliquid execution paths call the exchange clients.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy ORM/raw migrations, pytest, existing CEC-codex AI decision and trading command services.

---

## File Structure

- Create `backend/services/ai_review/__init__.py`: public exports for the review service.
- Create `backend/services/ai_review/schemas.py`: dataclasses/enums for review context, agent reports, final verdicts, and risk-limiting helpers.
- Create `backend/services/ai_review/context_builder.py`: converts the existing execution inputs into a `ReviewContext`.
- Create `backend/services/ai_review/agents/__init__.py`: reviewer exports.
- Create `backend/services/ai_review/agents/signal_reviewer.py`: wraps signal forward-validation verdicts.
- Create `backend/services/ai_review/agents/backtest_reviewer.py`: checks attached backtest evidence and marks missing evidence.
- Create `backend/services/ai_review/agents/loss_reviewer.py`: wraps existing pre-trade loss/exposure guard as a review report.
- Create `backend/services/ai_review/agents/execution_judge.py`: combines reviewer reports into the final risk-limited decision.
- Create `backend/services/ai_review/orchestrator.py`: builds and runs the reviewer pipeline.
- Create `backend/services/ai_review/persistence.py`: writes `ai_review_runs` and `ai_review_agent_reports`.
- Modify `backend/database/models/trading.py`: add review models and review columns on `AIDecisionLog`.
- Create `backend/database/migrations/add_ai_review_tables.py`: idempotent migration for review tables and decision-log columns.
- Modify `backend/database/migration_manager.py`: register the migration after existing decision/event migrations.
- Modify `backend/services/ai_decision_service/persistence.py`: persist `review_run_id`, `review_verdict`, and `review_blocked_reason` from the decision payload.
- Modify `backend/services/trading_commands/binance_execution.py`: invoke review before existing Binance gates and order placement.
- Modify `backend/services/trading_commands/hyperliquid_execution.py`: invoke review before Hyperliquid order placement.
- Create `backend/api/ai_review_routes.py`: read-only review run API.
- Modify `backend/main.py` and `backend/app_routers.py`: register the route.
- Add tests under `backend/tests/` for schemas, reviewers, judge, persistence migration registration, and execution wiring.

---

### Task 1: Add Review Schemas

**Files:**
- Create: `backend/services/ai_review/__init__.py`
- Create: `backend/services/ai_review/schemas.py`
- Test: `backend/tests/test_ai_review_schemas.py`

- [ ] **Step 1: Write the failing schema tests**

Create `backend/tests/test_ai_review_schemas.py`:

```python
from services.ai_review.schemas import (
    AgentReview,
    AgentVerdict,
    FinalReview,
    FinalVerdict,
    ReviewAdjustment,
    ReviewContext,
    clamp_final_review,
)


def test_review_context_normalizes_operation_and_environment():
    ctx = ReviewContext(
        account_id=7,
        account_name="review-bot",
        exchange="binance",
        environment="MAINNET",
        symbol="btc",
        operation="BUY",
        decision={"operation": "BUY", "symbol": "btc"},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 64000},
    )

    assert ctx.environment == "mainnet"
    assert ctx.symbol == "BTC"
    assert ctx.operation == "buy"
    assert ctx.is_opening_trade is True


def test_clamp_final_review_never_expands_risk():
    review = FinalReview(
        verdict=FinalVerdict.REDUCE_SIZE,
        symbol="BTC",
        operation="buy",
        max_target_portion=0.8,
        max_leverage=20,
        summary="judge tried to expand risk",
    )

    clamped = clamp_final_review(
        review,
        original_target_portion=0.25,
        original_leverage=5,
    )

    assert clamped.max_target_portion == 0.25
    assert clamped.max_leverage == 5


def test_agent_review_snapshot_is_json_ready():
    report = AgentReview(
        agent_role="signal_reviewer",
        verdict=AgentVerdict.BLOCK,
        confidence=0.9,
        evidence=[{"kind": "signal", "summary": "net pnl negative"}],
        blocking_reasons=["signal is not profitable"],
        report_text="Signal failed validation",
    )

    snapshot = report.to_snapshot()

    assert snapshot["agent_role"] == "signal_reviewer"
    assert snapshot["verdict"] == "block"
    assert snapshot["blocking_reasons"] == ["signal is not profitable"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_schemas.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.ai_review'`.

- [ ] **Step 3: Implement schema module**

Create `backend/services/ai_review/__init__.py`:

```python
"""Multi-agent review layer for AI trading decisions."""

from services.ai_review.schemas import (
    AgentReview,
    AgentVerdict,
    FinalReview,
    FinalVerdict,
    ReviewAdjustment,
    ReviewContext,
)

__all__ = [
    "AgentReview",
    "AgentVerdict",
    "FinalReview",
    "FinalVerdict",
    "ReviewAdjustment",
    "ReviewContext",
]
```

Create `backend/services/ai_review/schemas.py`:

```python
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
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_schemas.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_review/__init__.py backend/services/ai_review/schemas.py backend/tests/test_ai_review_schemas.py
git commit -m "Add AI review schema contracts"
```

---

### Task 2: Add Review Context Builder

**Files:**
- Create: `backend/services/ai_review/context_builder.py`
- Test: `backend/tests/test_ai_review_context_builder.py`

- [ ] **Step 1: Write context builder tests**

Create `backend/tests/test_ai_review_context_builder.py`:

```python
from services.ai_review.context_builder import build_review_context


class DummyAccount:
    id = 42
    name = "Decision Bot"


def test_build_review_context_extracts_decision_fields():
    ctx = build_review_context(
        account=DummyAccount(),
        decision={"operation": "sell", "symbol": "eth", "target_portion_of_balance": 0.4, "leverage": 8},
        portfolio={"total_assets": 5000},
        positions=[{"coin": "ETH", "szi": -0.2, "position_value": 800}],
        prices={"ETH": 3200},
        exchange="binance",
        environment="testnet",
        trigger_context={"trigger_type": "signal", "signal_trigger_id": 9},
        decision_kwargs={"prompt_template_id": 3},
    )

    assert ctx.account_id == 42
    assert ctx.account_name == "Decision Bot"
    assert ctx.exchange == "binance"
    assert ctx.environment == "testnet"
    assert ctx.symbol == "ETH"
    assert ctx.operation == "sell"
    assert ctx.signal_trigger_id == 9
    assert ctx.prompt_template_id == 3


def test_build_review_context_uses_decision_kwargs_signal_id_when_trigger_context_lacks_it():
    ctx = build_review_context(
        account=DummyAccount(),
        decision={"operation": "buy", "symbol": "btc"},
        portfolio={"total_assets": 5000},
        positions=[],
        prices={"BTC": 65000},
        exchange="hyperliquid",
        environment="mainnet",
        trigger_context={"trigger_type": "signal"},
        decision_kwargs={"signal_trigger_id": 77},
    )

    assert ctx.signal_trigger_id == 77
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_context_builder.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `build_review_context`.

- [ ] **Step 3: Implement context builder**

Create `backend/services/ai_review/context_builder.py`:

```python
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
```

- [ ] **Step 4: Run context builder tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_context_builder.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_review/context_builder.py backend/tests/test_ai_review_context_builder.py
git commit -m "Add AI review context builder"
```

---

### Task 3: Add Deterministic Reviewers

**Files:**
- Create: `backend/services/ai_review/agents/__init__.py`
- Create: `backend/services/ai_review/agents/signal_reviewer.py`
- Create: `backend/services/ai_review/agents/backtest_reviewer.py`
- Create: `backend/services/ai_review/agents/loss_reviewer.py`
- Test: `backend/tests/test_ai_review_agents.py`

- [ ] **Step 1: Write reviewer tests**

Create `backend/tests/test_ai_review_agents.py` with focused tests:

```python
from services.ai_review.agents.backtest_reviewer import BacktestReviewer
from services.ai_review.agents.loss_reviewer import LossReviewer
from services.ai_review.agents.signal_reviewer import SignalReviewer
from services.ai_review.schemas import AgentVerdict, ReviewContext


def _ctx(**overrides):
    data = {
        "account_id": 1,
        "account_name": "bot",
        "exchange": "binance",
        "environment": "mainnet",
        "symbol": "BTC",
        "operation": "buy",
        "decision": {"operation": "buy", "symbol": "BTC"},
        "portfolio": {"total_assets": 1000},
        "positions": [],
        "prices": {"BTC": 65000},
        "trigger_context": {"trigger_type": "scheduled"},
    }
    data.update(overrides)
    return ReviewContext(**data)


def test_signal_reviewer_passes_non_opening_trade(session):
    report = SignalReviewer().review(session, _ctx(operation="close"))
    assert report.verdict == AgentVerdict.PASS


def test_signal_reviewer_warns_on_scheduled_mainnet_open():
    report = SignalReviewer().review(session, _ctx(trigger_context={"trigger_type": "scheduled"}))
    assert report.verdict == AgentVerdict.WARN
    assert "非信号触发" in report.warnings[0]


def test_backtest_reviewer_warns_when_signal_has_no_backtest_summary(session):
    report = BacktestReviewer().review(session, _ctx(trigger_context={"trigger_type": "signal"}))
    assert report.verdict == AgentVerdict.WARN
    assert "缺少回测摘要" in report.warnings[0]


def test_backtest_reviewer_blocks_explicit_negative_backtest(session):
    report = BacktestReviewer().review(
        session,
        _ctx(trigger_context={"trigger_type": "signal", "backtest_summary": {"net_pnl": -12.5, "target_sample_met": True}}),
    )
    assert report.verdict == AgentVerdict.BLOCK
    assert "净盈亏为负" in report.blocking_reasons[0]


def test_loss_reviewer_blocks_existing_risk_guard_failure(session):
    report = LossReviewer().review(
        session,
        _ctx(positions=[{"coin": "BTC", "szi": 1.0, "position_value": 500, "unrealized_pnl": -15.0}]),
    )
    assert report.verdict == AgentVerdict.BLOCK
    assert "风控闸" in report.blocking_reasons[0]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_agents.py -q
```

Expected: FAIL because the reviewer modules do not exist.

- [ ] **Step 3: Implement reviewers**

Create `backend/services/ai_review/agents/__init__.py`:

```python
"""Review agent exports."""

from services.ai_review.agents.backtest_reviewer import BacktestReviewer
from services.ai_review.agents.loss_reviewer import LossReviewer
from services.ai_review.agents.signal_reviewer import SignalReviewer

__all__ = ["BacktestReviewer", "LossReviewer", "SignalReviewer"]
```

Create `backend/services/ai_review/agents/signal_reviewer.py`:

```python
"""Signal validation reviewer."""
from __future__ import annotations

from sqlalchemy.orm import Session

from services.ai_review.schemas import AgentReview, AgentVerdict, ReviewContext


class SignalReviewer:
    role = "signal_reviewer"

    def review(self, db: Session, context: ReviewContext) -> AgentReview:
        if not context.is_opening_trade:
            return AgentReview(self.role, AgentVerdict.PASS, 1.0, report_text="非新增仓位动作不需要信号验证。")

        trigger_type = (context.trigger_context or {}).get("trigger_type")
        if trigger_type != "signal":
            return AgentReview(
                self.role,
                AgentVerdict.WARN,
                0.6,
                warnings=["非信号触发的新增仓位只能作为低置信度决策处理。"],
                report_text="该决策不是由信号池触发，后续执行裁判应限制主网风险。",
            )

        if context.environment == "mainnet":
            from services.signal_trigger_validation import signal_validation_gate

            gate = signal_validation_gate(db, context.trigger_context)
            if not gate["allowed"]:
                return AgentReview(
                    self.role,
                    AgentVerdict.BLOCK,
                    0.95,
                    evidence=[{"kind": "signal_validation_gate", "record": gate.get("record")}],
                    blocking_reasons=[gate["reason"]],
                    report_text=gate["reason"],
                )

        return AgentReview(
            self.role,
            AgentVerdict.PASS,
            0.85,
            evidence=[{"kind": "signal_trigger", "signal_trigger_id": context.signal_trigger_id}],
            report_text="信号触发上下文存在，未命中信号阻断条件。",
        )
```

Create `backend/services/ai_review/agents/backtest_reviewer.py`:

```python
"""Backtest evidence reviewer."""
from __future__ import annotations

from sqlalchemy.orm import Session

from services.ai_review.schemas import AgentReview, AgentVerdict, ReviewContext


class BacktestReviewer:
    role = "backtest_reviewer"

    def review(self, db: Session, context: ReviewContext) -> AgentReview:
        if not context.is_opening_trade:
            return AgentReview(self.role, AgentVerdict.PASS, 1.0, report_text="非新增仓位动作不要求开仓回测摘要。")

        summary = (context.trigger_context or {}).get("backtest_summary")
        if not summary:
            return AgentReview(
                self.role,
                AgentVerdict.WARN,
                0.55,
                warnings=["缺少回测摘要，不能证明该触发条件已通过样本外验证。"],
                report_text="未发现结构化 backtest_summary，第一版仅发出风险警告。",
            )

        net_pnl = float(summary.get("net_pnl") or 0)
        sample_met = bool(summary.get("target_sample_met"))
        slippage_bps = summary.get("slippage_bps")
        if net_pnl < 0:
            return AgentReview(
                self.role,
                AgentVerdict.BLOCK,
                0.9,
                evidence=[{"kind": "backtest_summary", "summary": summary}],
                blocking_reasons=[f"回测净盈亏为负：{net_pnl:.2f}"],
                report_text="回测净盈亏为负，不能驱动新增仓位。",
            )
        if not sample_met:
            return AgentReview(
                self.role,
                AgentVerdict.TESTNET_ONLY,
                0.8,
                evidence=[{"kind": "backtest_summary", "summary": summary}],
                warnings=["回测未通过最小样本门槛。"],
                report_text="样本不足，建议仅在测试网继续观察。",
            )
        if slippage_bps in (None, 0):
            return AgentReview(
                self.role,
                AgentVerdict.WARN,
                0.7,
                evidence=[{"kind": "backtest_summary", "summary": summary}],
                warnings=["回测未计入滑点或滑点为 0。"],
                report_text="回测盈利但执行成本假设偏乐观。",
            )
        return AgentReview(
            self.role,
            AgentVerdict.PASS,
            0.85,
            evidence=[{"kind": "backtest_summary", "summary": summary}],
            report_text="回测摘要通过净盈亏、样本量和滑点检查。",
        )
```

Create `backend/services/ai_review/agents/loss_reviewer.py`:

```python
"""Loss and exposure reviewer."""
from __future__ import annotations

from sqlalchemy.orm import Session

from services.ai_review.schemas import AgentReview, AgentVerdict, ReviewContext


class LossReviewer:
    role = "loss_reviewer"

    def review(self, db: Session, context: ReviewContext) -> AgentReview:
        if not context.is_opening_trade or not context.symbol:
            return AgentReview(self.role, AgentVerdict.PASS, 1.0, report_text="非新增仓位不触发亏损加仓审查。")

        from services.trading_commands.risk_guards import check_pre_trade_guards

        guard = check_pre_trade_guards(
            db,
            account_id=context.account_id,
            symbol=context.symbol,
            operation=context.operation,
            positions=context.positions,
            total_equity=float(context.portfolio.get("total_assets") or 0),
        )
        if not guard["allowed"]:
            return AgentReview(
                self.role,
                AgentVerdict.BLOCK,
                0.95,
                blocking_reasons=[guard["reason"]],
                report_text=guard["reason"],
            )
        return AgentReview(
            self.role,
            AgentVerdict.PASS,
            0.85,
            report_text="未命中连亏、同向敞口或亏损持仓加仓阻断。",
        )
```

- [ ] **Step 4: Run reviewer tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_agents.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_review/agents backend/tests/test_ai_review_agents.py
git commit -m "Add deterministic AI review agents"
```

---

### Task 4: Add Execution Judge and Orchestrator

**Files:**
- Create: `backend/services/ai_review/agents/execution_judge.py`
- Create: `backend/services/ai_review/orchestrator.py`
- Test: `backend/tests/test_ai_review_orchestrator.py`

- [ ] **Step 1: Write judge and orchestrator tests**

Create `backend/tests/test_ai_review_orchestrator.py`:

```python
from services.ai_review.agents.execution_judge import ExecutionJudge
from services.ai_review.orchestrator import apply_final_review_to_decision
from services.ai_review.schemas import AgentReview, AgentVerdict, FinalVerdict, ReviewAdjustment, ReviewContext


def _ctx():
    return ReviewContext(
        account_id=1,
        account_name="bot",
        exchange="binance",
        environment="mainnet",
        symbol="BTC",
        operation="buy",
        decision={"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 65000},
    )


def test_execution_judge_blocks_when_any_agent_blocks():
    final = ExecutionJudge().judge(
        _ctx(),
        [AgentReview("loss_reviewer", AgentVerdict.BLOCK, 0.9, blocking_reasons=["loss streak"])],
    )

    assert final.verdict == FinalVerdict.BLOCK
    assert final.blocking_reasons == ["loss streak"]


def test_execution_judge_reduces_to_smallest_reviewer_limit():
    final = ExecutionJudge().judge(
        _ctx(),
        [
            AgentReview("a", AgentVerdict.WARN, 0.7, recommended_adjustments=ReviewAdjustment(max_target_portion=0.2)),
            AgentReview("b", AgentVerdict.WARN, 0.7, recommended_adjustments=ReviewAdjustment(max_leverage=3)),
        ],
    )

    assert final.verdict == FinalVerdict.REDUCE_SIZE
    assert final.max_target_portion == 0.2
    assert final.max_leverage == 3


def test_apply_final_review_blocks_without_exchange_execution():
    decision = {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10}
    final = ExecutionJudge().judge(
        _ctx(),
        [AgentReview("loss_reviewer", AgentVerdict.BLOCK, 0.9, blocking_reasons=["loss streak"])],
    )

    result = apply_final_review_to_decision(decision, final)

    assert result["allowed"] is False
    assert decision["review_verdict"] == "block"
    assert decision["review_blocked_reason"] == "loss streak"
    assert decision["review_result"]["verdict"] == "block"


def test_apply_final_review_reduces_size_and_leverage():
    decision = {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.4, "leverage": 10}
    final = ExecutionJudge().judge(
        _ctx(),
        [AgentReview("risk", AgentVerdict.WARN, 0.8, recommended_adjustments=ReviewAdjustment(max_target_portion=0.1, max_leverage=2))],
    )

    result = apply_final_review_to_decision(decision, final)

    assert result["allowed"] is True
    assert decision["target_portion_of_balance"] == 0.1
    assert decision["leverage"] == 2
    assert decision["review_verdict"] == "reduce_size"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_orchestrator.py -q
```

Expected: FAIL because execution judge and orchestrator do not exist.

- [ ] **Step 3: Implement judge and orchestrator**

Create `backend/services/ai_review/agents/execution_judge.py`:

```python
"""Final execution judge for AI review reports."""
from __future__ import annotations

from typing import List

from services.ai_review.schemas import AgentReview, AgentVerdict, FinalReview, FinalVerdict, ReviewContext


class ExecutionJudge:
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
            adj = report.recommended_adjustments
            if adj.max_target_portion is not None:
                max_portion = min(max_portion, adj.max_target_portion)
            if adj.max_leverage is not None:
                max_leverage = min(max_leverage, adj.max_leverage)

        if max_portion < original_portion or max_leverage < original_leverage or any(r.verdict == AgentVerdict.WARN for r in reports):
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
```

Create `backend/services/ai_review/orchestrator.py`:

```python
"""Run AI decision reviews and apply final verdicts."""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from services.ai_review.agents import BacktestReviewer, LossReviewer, SignalReviewer
from services.ai_review.agents.execution_judge import ExecutionJudge
from services.ai_review.schemas import FinalReview, FinalVerdict, ReviewContext


def run_review_pipeline(db: Session, context: ReviewContext) -> FinalReview:
    reports = [
        SignalReviewer().review(db, context),
        BacktestReviewer().review(db, context),
        LossReviewer().review(db, context),
    ]
    return ExecutionJudge().judge(context, reports)


def apply_final_review_to_decision(decision: Dict[str, Any], review: FinalReview) -> Dict[str, Any]:
    decision["review_result"] = review.to_snapshot()
    decision["review_verdict"] = review.verdict.value
    decision["review_blocked_reason"] = "; ".join(review.blocking_reasons) if review.blocking_reasons else None

    if review.review_run_id is not None:
        decision["review_run_id"] = review.review_run_id

    if review.verdict in {FinalVerdict.BLOCK, FinalVerdict.HOLD}:
        return {"allowed": False, "reason": decision.get("review_blocked_reason") or review.summary}

    if review.verdict == FinalVerdict.REDUCE_SIZE:
        if "target_portion_of_balance" in decision:
            decision["target_portion_of_balance"] = min(
                float(decision.get("target_portion_of_balance") or 0),
                review.max_target_portion,
            )
        if "leverage" in decision:
            decision["leverage"] = min(int(decision.get("leverage") or 1), review.max_leverage)

    return {"allowed": True, "reason": review.summary}
```

- [ ] **Step 4: Run judge/orchestrator tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_orchestrator.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_review/agents/execution_judge.py backend/services/ai_review/orchestrator.py backend/tests/test_ai_review_orchestrator.py
git commit -m "Add AI review execution judge"
```

---

### Task 5: Add Persistence and Migration

**Files:**
- Modify: `backend/database/models/trading.py`
- Create: `backend/database/migrations/add_ai_review_tables.py`
- Modify: `backend/database/migration_manager.py`
- Create: `backend/services/ai_review/persistence.py`
- Modify: `backend/services/ai_decision_service/persistence.py`
- Test: `backend/tests/test_ai_review_persistence_static.py`

- [ ] **Step 1: Write static persistence tests**

Create `backend/tests/test_ai_review_persistence_static.py`:

```python
from pathlib import Path

from database import migration_manager


ROOT = Path(__file__).resolve().parents[1]


def test_ai_review_migration_registered():
    assert "add_ai_review_tables.py" in migration_manager.MIGRATIONS


def test_ai_review_models_declared():
    text = (ROOT / "database" / "models" / "trading.py").read_text()
    assert "class AIReviewRun" in text
    assert "class AIReviewAgentReport" in text
    assert "review_run_id" in text
    assert "review_verdict" in text
    assert "review_blocked_reason" in text


def test_save_ai_decision_persists_review_fields():
    text = (ROOT / "services" / "ai_decision_service" / "persistence.py").read_text()
    assert "review_run_id=decision.get(\"review_run_id\")" in text
    assert "review_verdict=decision.get(\"review_verdict\")" in text
    assert "review_blocked_reason=decision.get(\"review_blocked_reason\")" in text
```

- [ ] **Step 2: Run static tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_persistence_static.py -q
```

Expected: FAIL because models, migration, and persistence fields are missing.

- [ ] **Step 3: Modify models**

In `backend/database/models/trading.py`, add these columns to `AIDecisionLog` after `exchange`:

```python
    review_run_id = Column(Integer, nullable=True, index=True)
    review_verdict = Column(String(20), nullable=True)
    review_blocked_reason = Column(Text, nullable=True)
```

Add these model classes after `AIDecisionLog`:

```python
class AIReviewRun(Base):
    __tablename__ = "ai_review_runs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    decision_log_id = Column(Integer, ForeignKey("ai_decision_logs.id"), nullable=True, index=True)
    exchange = Column(String(20), nullable=True, index=True)
    environment = Column(String(20), nullable=True, index=True)
    symbol = Column(String(20), nullable=True, index=True)
    operation = Column(String(10), nullable=False)
    original_target_portion = Column(DECIMAL(10, 6), nullable=True)
    original_leverage = Column(Integer, nullable=True)
    verdict = Column(String(20), nullable=False, index=True)
    final_target_portion = Column(DECIMAL(10, 6), nullable=True)
    final_leverage = Column(Integer, nullable=True)
    final_reason = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    account = relationship("Account")
    decision_log = relationship("AIDecisionLog")


class AIReviewAgentReport(Base):
    __tablename__ = "ai_review_agent_reports"

    id = Column(Integer, primary_key=True, index=True)
    review_run_id = Column(Integer, ForeignKey("ai_review_runs.id"), nullable=False, index=True)
    agent_role = Column(String(50), nullable=False, index=True)
    verdict = Column(String(20), nullable=False, index=True)
    confidence = Column(DECIMAL(5, 4), nullable=True)
    report_json = Column(Text, nullable=True)
    report_text = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    review_run = relationship("AIReviewRun")
```

- [ ] **Step 4: Add idempotent migration**

Create `backend/database/migrations/add_ai_review_tables.py`:

```python
#!/usr/bin/env python3
"""Create AI review tables and decision-log review columns."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from database.connection import engine


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
        )
    """), {"table_name": table_name, "column_name": column_name})
    return bool(result.scalar())


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table_name
        )
    """), {"table_name": table_name})
    return bool(result.scalar())


def upgrade() -> None:
    with engine.connect() as conn:
        if not _table_exists(conn, "ai_review_runs"):
            conn.execute(text("""
                CREATE TABLE ai_review_runs (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    decision_log_id INTEGER REFERENCES ai_decision_logs(id),
                    exchange VARCHAR(20),
                    environment VARCHAR(20),
                    symbol VARCHAR(20),
                    operation VARCHAR(10) NOT NULL,
                    original_target_portion DECIMAL(10, 6),
                    original_leverage INTEGER,
                    verdict VARCHAR(20) NOT NULL,
                    final_target_portion DECIMAL(10, 6),
                    final_leverage INTEGER,
                    final_reason TEXT,
                    latency_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        if not _table_exists(conn, "ai_review_agent_reports"):
            conn.execute(text("""
                CREATE TABLE ai_review_agent_reports (
                    id SERIAL PRIMARY KEY,
                    review_run_id INTEGER NOT NULL REFERENCES ai_review_runs(id),
                    agent_role VARCHAR(50) NOT NULL,
                    verdict VARCHAR(20) NOT NULL,
                    confidence DECIMAL(5, 4),
                    report_json TEXT,
                    report_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        for column, ddl in (
            ("review_run_id", "ALTER TABLE ai_decision_logs ADD COLUMN review_run_id INTEGER"),
            ("review_verdict", "ALTER TABLE ai_decision_logs ADD COLUMN review_verdict VARCHAR(20)"),
            ("review_blocked_reason", "ALTER TABLE ai_decision_logs ADD COLUMN review_blocked_reason TEXT"),
        ):
            if not _column_exists(conn, "ai_decision_logs", column):
                conn.execute(text(ddl))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_ai_review_runs_account_id ON ai_review_runs(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_review_runs_symbol ON ai_review_runs(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_ai_review_runs_verdict ON ai_review_runs(verdict)",
            "CREATE INDEX IF NOT EXISTS idx_ai_review_agent_reports_run_id ON ai_review_agent_reports(review_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decision_logs_review_run_id ON ai_decision_logs(review_run_id)",
        ):
            conn.execute(text(stmt))
        conn.commit()


if __name__ == "__main__":
    upgrade()
```

- [ ] **Step 5: Register migration and persistence fields**

In `backend/database/migration_manager.py`, add the migration at the end of the `MIGRATIONS` list so the final lines read:

```python
    "add_event_contract_validation_log.py",
    "add_ai_review_tables.py",
]
```

In `backend/services/ai_decision_service/persistence.py`, pass review fields into `the `AIDecisionLog` constructor` after `exchange=exchange`:

```python
            review_run_id=decision.get("review_run_id"),
            review_verdict=decision.get("review_verdict"),
            review_blocked_reason=decision.get("review_blocked_reason"),
```

- [ ] **Step 6: Add persistence helper**

Create `backend/services/ai_review/persistence.py`:

```python
"""Persistence helpers for AI review reports."""
from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from database.models.trading import AIReviewAgentReport, AIReviewRun
from services.ai_review.schemas import FinalReview, ReviewContext


def save_review_run(
    db: Session,
    context: ReviewContext,
    review: FinalReview,
    *,
    started_at: Optional[float] = None,
) -> FinalReview:
    latency_ms = None
    if started_at is not None:
        latency_ms = int((time.monotonic() - started_at) * 1000)

    run = AIReviewRun(
        account_id=context.account_id,
        exchange=context.exchange,
        environment=context.environment,
        symbol=context.symbol,
        operation=context.operation,
        original_target_portion=Decimal(str(context.decision.get("target_portion_of_balance") or 0)),
        original_leverage=int(context.decision.get("leverage") or 1),
        verdict=review.verdict.value,
        final_target_portion=Decimal(str(review.max_target_portion)),
        final_leverage=review.max_leverage,
        final_reason=review.summary,
        latency_ms=latency_ms,
    )
    db.add(run)
    db.flush()

    for report in review.agent_reports:
        db.add(AIReviewAgentReport(
            review_run_id=run.id,
            agent_role=report.agent_role,
            verdict=report.verdict.value,
            confidence=Decimal(str(report.confidence)),
            report_json=json.dumps(report.to_snapshot(), ensure_ascii=False),
            report_text=report.report_text,
        ))
    db.commit()
    review.review_run_id = run.id
    return review
```

- [ ] **Step 7: Run persistence static tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_persistence_static.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/database/models/trading.py backend/database/migrations/add_ai_review_tables.py backend/database/migration_manager.py backend/services/ai_review/persistence.py backend/services/ai_decision_service/persistence.py backend/tests/test_ai_review_persistence_static.py
git commit -m "Persist AI review reports"
```

---

### Task 6: Wire Review Layer into Binance and Hyperliquid Execution

**Files:**
- Modify: `backend/services/ai_review/orchestrator.py`
- Modify: `backend/services/trading_commands/binance_execution.py`
- Modify: `backend/services/trading_commands/hyperliquid_execution.py`
- Test: `backend/tests/test_ai_review_execution_wiring.py`

- [ ] **Step 1: Write execution wiring tests**

Create `backend/tests/test_ai_review_execution_wiring.py`:

```python
from services.ai_review.schemas import FinalReview, FinalVerdict


class _ExplodingClient:
    def place_order_with_tpsl(self, *args, **kwargs):
        raise AssertionError("exchange client must not be called after review block")


class _Account:
    id = 1
    name = "reviewed"
    model = "test-model"


def _blocked_review():
    return FinalReview(
        verdict=FinalVerdict.BLOCK,
        symbol="BTC",
        operation="buy",
        max_target_portion=0,
        max_leverage=1,
        summary="blocked by review",
        blocking_reasons=["blocked by review"],
    )


def test_binance_review_block_saves_without_exchange_call(session, monkeypatch):
    from services.trading_commands import binance_execution

    saved = []
    monkeypatch.setattr(
        binance_execution,
        "save_ai_decision",
        lambda *args, **kwargs: saved.append({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        "services.ai_review.orchestrator.review_and_apply",
        lambda *args, **kwargs: {"allowed": False, "review": _blocked_review(), "reason": "blocked by review"},
    )

    binance_execution._execute_binance_decision(
        session,
        _Account(),
        _ExplodingClient(),
        {"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.2, "leverage": 3},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 65000},
        available_balance=900,
    )

    assert len(saved) == 1
    assert saved[0]["args"][4] is False


def test_hyperliquid_review_block_saves_without_entry_order(session, monkeypatch):
    from services.trading_commands import hyperliquid_execution

    saved = []
    monkeypatch.setattr(
        hyperliquid_execution,
        "save_ai_decision",
        lambda *args, **kwargs: saved.append({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        "services.ai_review.orchestrator.review_and_apply",
        lambda *args, **kwargs: {"allowed": False, "review": _blocked_review(), "reason": "blocked by review"},
    )
    monkeypatch.setattr(
        hyperliquid_execution,
        "_execute_entry_order",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("entry order blocked")),
    )

    hyperliquid_execution._execute_hyperliquid_decision(
        db=session,
        account=_Account(),
        client=object(),
        decision={"operation": "buy", "symbol": "BTC", "target_portion_of_balance": 0.2, "leverage": 3},
        portfolio={"total_assets": 1000},
        positions=[],
        prices={"BTC": 65000},
        available_balance=900,
        environment="testnet",
    )

    assert len(saved) == 1
    assert saved[0]["args"][4] is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_execution_wiring.py -q
```

Expected: FAIL because `review_and_apply` is not implemented and execution paths do not call it.

- [ ] **Step 3: Add orchestration helper**

Append to `backend/services/ai_review/orchestrator.py`:

```python
import time

from services.ai_review.context_builder import build_review_context
from services.ai_review.persistence import save_review_run


def review_and_apply(
    db: Session,
    *,
    account,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    exchange: str,
    environment: str,
    trigger_context=None,
    decision_kwargs=None,
) -> Dict[str, Any]:
    if (decision.get("operation") or "").lower() in {"close", "hold"}:
        return {"allowed": True, "review": None, "reason": "risk-reducing operation"}

    started_at = time.monotonic()
    context = build_review_context(
        account=account,
        decision=decision,
        portfolio=portfolio,
        positions=positions,
        prices=prices,
        exchange=exchange,
        environment=environment,
        trigger_context=trigger_context,
        decision_kwargs=decision_kwargs,
    )
    review = run_review_pipeline(db, context)
    review = save_review_run(db, context, review, started_at=started_at)
    applied = apply_final_review_to_decision(decision, review)
    return {"allowed": applied["allowed"], "review": review, "reason": applied["reason"]}
```

- [ ] **Step 4: Call review from Binance execution**

In `backend/services/trading_commands/binance_execution.py`, before the existing mainnet signal validation block, insert:

```python
    if operation in ("buy", "sell"):
        from services.ai_review.orchestrator import review_and_apply

        review_result = review_and_apply(
            db,
            account=account,
            decision=decision,
            portfolio=portfolio,
            positions=positions,
            prices=prices,
            exchange="binance",
            environment=wallet.environment if wallet is not None else "paper",
            trigger_context=trigger_context,
            decision_kwargs=decision_kwargs,
        )
        if not review_result["allowed"]:
            logger.warning(
                "[BINANCE] AI review blocked %s %s for %s: %s",
                operation,
                symbol,
                account.name,
                review_result["reason"],
            )
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return
```

- [ ] **Step 5: Call review from Hyperliquid execution**

In `backend/services/trading_commands/hyperliquid_execution.py`, before `check_pre_trade_guards`, insert:

```python
        from services.ai_review.orchestrator import review_and_apply

        review_result = review_and_apply(
            db,
            account=account,
            decision=decision,
            portfolio=portfolio,
            positions=positions,
            prices=prices,
            exchange="hyperliquid",
            environment=environment,
            trigger_context=trigger_context,
            decision_kwargs=decision_kwargs,
        )
        if not review_result["allowed"]:
            logger.warning(
                "AI review blocked %s %s for %s: %s",
                operation,
                symbol,
                account.name,
                review_result["reason"],
            )
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return
```

- [ ] **Step 6: Run execution wiring tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_execution_wiring.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/services/ai_review/orchestrator.py backend/services/trading_commands/binance_execution.py backend/services/trading_commands/hyperliquid_execution.py backend/tests/test_ai_review_execution_wiring.py
git commit -m "Gate exchange execution with AI review"
```

---

### Task 7: Add Read-Only Review API

**Files:**
- Create: `backend/api/ai_review_routes.py`
- Modify: `backend/main.py`
- Modify: `backend/app_routers.py`
- Test: `backend/tests/test_ai_review_routes_static.py`

- [ ] **Step 1: Write route static tests**

Create `backend/tests/test_ai_review_routes_static.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ai_review_routes_declared():
    text = (ROOT / "api" / "ai_review_routes.py").read_text()
    assert "router = APIRouter(prefix=\"/api/ai-review\", tags=[\"AI Review\"])" in text
    assert "def list_review_runs" in text
    assert "def get_review_run" in text


def test_ai_review_router_registered_in_live_main():
    text = (ROOT / "main.py").read_text()
    assert "from api.ai_review_routes import router as ai_review_router" in text
    assert "app.include_router(ai_review_router)" in text


def test_ai_review_router_registered_in_split_router_module():
    text = (ROOT / "app_routers.py").read_text()
    assert "from api.ai_review_routes import router as ai_review_router" in text
    assert "app.include_router(ai_review_router)" in text
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_routes_static.py -q
```

Expected: FAIL because route file and registrations do not exist.

- [ ] **Step 3: Implement routes**

Create `backend/api/ai_review_routes.py`:

```python
"""Read-only APIs for AI review runs."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models.trading import AIReviewAgentReport, AIReviewRun

router = APIRouter(prefix="/api/ai-review", tags=["AI Review"])


def _run_to_dict(run: AIReviewRun) -> dict:
    return {
        "id": run.id,
        "account_id": run.account_id,
        "decision_log_id": run.decision_log_id,
        "exchange": run.exchange,
        "environment": run.environment,
        "symbol": run.symbol,
        "operation": run.operation,
        "verdict": run.verdict,
        "final_reason": run.final_reason,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/runs")
def list_review_runs(
    account_id: Optional[int] = Query(None),
    verdict: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(AIReviewRun).order_by(AIReviewRun.created_at.desc())
    if account_id is not None:
        query = query.filter(AIReviewRun.account_id == account_id)
    if verdict:
        query = query.filter(AIReviewRun.verdict == verdict)
    return {"items": [_run_to_dict(run) for run in query.limit(limit).all()]}


@router.get("/runs/{run_id}")
def get_review_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AIReviewRun).filter(AIReviewRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Review run not found")
    reports = db.query(AIReviewAgentReport).filter(
        AIReviewAgentReport.review_run_id == run_id
    ).order_by(AIReviewAgentReport.id.asc()).all()
    data = _run_to_dict(run)
    data["agent_reports"] = [
        {
            "agent_role": report.agent_role,
            "verdict": report.verdict,
            "confidence": float(report.confidence) if report.confidence is not None else None,
            "report": json.loads(report.report_json) if report.report_json else None,
            "report_text": report.report_text,
        }
        for report in reports
    ]
    return data
```

- [ ] **Step 4: Register route**

In `backend/main.py`, add import near other router imports:

```python
from api.ai_review_routes import router as ai_review_router
```

Add include near analytics routes:

```python
app.include_router(ai_review_router)
```

In `backend/app_routers.py`, add the same import and include line inside `register_routers(app)` near analytics routes.

- [ ] **Step 5: Run route tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_ai_review_routes_static.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/ai_review_routes.py backend/main.py backend/app_routers.py backend/tests/test_ai_review_routes_static.py
git commit -m "Add AI review read APIs"
```

---

### Task 8: Verification Pass

**Files:**
- No source files created in this task.

- [ ] **Step 1: Run targeted AI review tests**

Run:

```bash
uv run --project backend pytest \
  backend/tests/test_ai_review_schemas.py \
  backend/tests/test_ai_review_context_builder.py \
  backend/tests/test_ai_review_agents.py \
  backend/tests/test_ai_review_orchestrator.py \
  backend/tests/test_ai_review_persistence_static.py \
  backend/tests/test_ai_review_execution_wiring.py \
  backend/tests/test_ai_review_routes_static.py -q
```

Expected: all targeted tests PASS.

- [ ] **Step 2: Run related regression tests**

Run:

```bash
uv run --project backend pytest \
  backend/tests/test_signal_trigger_validation.py \
  backend/tests/test_loss_attribution.py \
  backend/tests/test_pre_trade_risk_guards.py \
  backend/tests/test_decision_self_consistency.py \
  backend/tests/test_decision_outcome_prompt_context.py \
  backend/tests/test_prompt_backtest_guard_parity.py -q
```

Expected: all related regression tests PASS.

- [ ] **Step 3: Run lint on touched backend areas**

Run:

```bash
uv run --project backend ruff check backend/services/ai_review backend/api/ai_review_routes.py backend/database/migrations/add_ai_review_tables.py backend/services/trading_commands/binance_execution.py backend/services/trading_commands/hyperliquid_execution.py backend/services/ai_decision_service/persistence.py
```

Expected: no ruff errors.

- [ ] **Step 4: Check diff hygiene**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Stop before implementation completion claim**

Before reporting the implementation complete, use `superpowers:verification-before-completion` and include the exact passing command output in the final status.
