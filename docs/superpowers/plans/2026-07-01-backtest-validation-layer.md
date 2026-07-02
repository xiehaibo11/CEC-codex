# Backtest Validation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic backtest validation report with walk-forward windows, Monte Carlo sequence-risk stress, regime stability, and conservative live-decay estimates.

**Architecture:** Create a focused backend module `backend/services/event_contract/backtest_validation.py` and call it from `EventContractBacktestHelperMixin._build_summary`. Extend frontend API types and render a compact validation panel in `BacktestResultsPanel`.

**Tech Stack:** Python 3.12, pytest, ruff, FastAPI response JSON, React/Vite TypeScript, i18next.

---

### Task 1: Backend validation report tests

**Files:**
- Modify: `backend/tests/test_event_contract_backtest.py`

- [ ] Add `test_validation_report_flags_walk_forward_regime_and_decay_risk` that builds synthetic trades with one weak regime and asserts `summary["validation_report"]` contains walk-forward, monte-carlo, regime-stability, and live-decay sections.
- [ ] Run the new test alone and verify it fails with missing `validation_report`.

### Task 2: Backend validation report implementation

**Files:**
- Create: `backend/services/event_contract/backtest_validation.py`
- Modify: `backend/services/event_contract/backtest_helpers.py`

- [ ] Implement deterministic helpers for max drawdown, percentiles, trade windows, Monte Carlo shuffles, regime grouping, and live-decay verdict.
- [ ] Attach `summary["validation_report"]` from `_build_summary`.
- [ ] Run the new backend test and verify it passes.

### Task 3: Backend regression verification

**Files:**
- Modify only if tests expose integration issues.

- [ ] Run `cd backend && uv run pytest tests/test_event_contract_backtest.py tests/test_event_contract_backtest_tasks.py -q`.
- [ ] Run ruff on changed backend files.

### Task 4: Frontend types and panel

**Files:**
- Modify: `frontend/app/lib/eventContractApi.ts`
- Modify: `frontend/app/components/backtest/BacktestResultsPanel.tsx`
- Modify: `frontend/app/locales/en.json`
- Modify: `frontend/app/locales/zh.json`

- [ ] Add TypeScript interfaces for `validation_report`.
- [ ] Render `ValidationReportPanel` near `QualityGatePanel`.
- [ ] Add bilingual labels.
- [ ] Run `pnpm build:frontend`.

### Task 5: Runtime smoke

**Files:**
- Runtime only.

- [ ] Verify `/api/health`.
- [ ] Run a direct Python smoke sample using `_build_summary` and print `validation_report` headline fields.
