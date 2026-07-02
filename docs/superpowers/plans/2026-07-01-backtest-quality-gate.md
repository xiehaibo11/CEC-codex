# Backtest Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a quality gate and credibility score to event-contract backtest summaries so users can judge whether a high win rate is trustworthy.

**Architecture:** Add a focused backend helper that evaluates existing backtest config, summary inputs, skipped counters, and data-quality audits, then attaches a `quality_gate` object to the existing summary. Surface that object in the existing backtest results panel without changing settlement math, task persistence shape, or reviewer voting.

**Tech Stack:** Python 3.12, FastAPI service modules, pytest, React/Vite/TypeScript/i18next.

---

### Task 1: Backend quality gate helper

**Files:**
- Create: `backend/services/event_contract/backtest_quality.py`
- Modify: `backend/services/event_contract/backtest_helpers.py`
- Test: `backend/tests/test_event_contract_backtest.py`

- [x] Step 1: Add failing tests for quality gate sample, partial, zero-cost, nested data warnings, and high-quality cases.
- [x] Step 2: Run targeted pytest and verify the new tests fail because `quality_gate` is missing.
- [x] Step 3: Implement `build_backtest_quality_gate` and attach it in `_build_summary`.
- [x] Step 4: Run targeted pytest and verify the new tests pass.

### Task 2: Frontend API types and result UI

**Files:**
- Modify: `frontend/app/lib/eventContractApi.ts`
- Modify: `frontend/app/components/backtest/BacktestResultsPanel.tsx`
- Modify: `frontend/app/locales/en.json`
- Modify: `frontend/app/locales/zh.json`

- [x] Step 1: Extend TypeScript summary type with `quality_gate`.
- [x] Step 2: Render a compact Quality Gate section with grade, score, status, failed/warning checks, and recommendations.
- [x] Step 3: Add bilingual locale keys.
- [x] Step 4: Run frontend build if practical.

### Task 3: Verification

**Files:**
- Verify backend tests.
- Verify Python lint on touched backend modules if practical.
- Verify frontend build if practical.

- [x] Step 1: Run `cd backend && uv run pytest tests/test_event_contract_backtest.py`.
- [x] Step 2: Run `cd backend && uv run ruff check services/event_contract/backtest_quality.py services/event_contract/backtest_helpers.py tests/test_event_contract_backtest.py`.
- [x] Step 3: Run `pnpm build:frontend`.
- [x] Step 4: Report changed files and verification evidence.
