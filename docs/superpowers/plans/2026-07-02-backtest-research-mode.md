# Backtest Research Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automatic research-mode report to Backtest Tool so each event-contract backtest surfaces OOS validation, candidate strategies, factor discovery, overfitting warnings, and missing-data recommendations instead of only displaying aggregate win rate.

**Architecture:** Backend computes a deterministic `research_report` from settled trades and factor snapshots inside `_build_summary`; frontend extends API types and adds a Research Mode tab in `BacktestResultsPanel`. The report does not change settlement math or trade selection.

**Tech Stack:** FastAPI/Python service helpers, pytest, React/TypeScript, i18next, Vite.

---

### Task 1: Backend research report tests

**Files:**
- Modify: `backend/tests/test_event_contract_backtest.py`

- [ ] Add a test that builds synthetic trades with factor snapshots, calls `_build_summary`, and asserts `summary["research_report"]` contains OOS validation, candidate strategies, factor insights, overfit warnings, and data recommendations.
- [ ] Run `cd backend && uv run pytest tests/test_event_contract_backtest.py::test_research_report_detects_oos_decay_candidates_and_missing_data -q` and confirm it fails because `research_report` is missing.

### Task 2: Backend research report implementation

**Files:**
- Create: `backend/services/event_contract/backtest_research.py`
- Modify: `backend/services/event_contract/backtest_helpers.py`

- [ ] Implement `build_backtest_research_report(cfg, trades, skipped, data_quality, summary)`.
- [ ] Include sections: `verdict`, `oos_validation`, `strategy_candidates`, `factor_insights`, `overfitting_warnings`, `missing_data_recommendations`.
- [ ] Keep all calculations deterministic and based only on settled trades.
- [ ] Attach `summary["research_report"]` after quality and validation reports.
- [ ] Re-run the backend test and confirm it passes.

### Task 3: Frontend API types and Research tab

**Files:**
- Modify: `frontend/app/lib/eventContractApi.ts`
- Modify: `frontend/app/components/backtest/BacktestResultsPanel.tsx`
- Modify: `frontend/app/locales/zh.json`
- Modify: `frontend/app/locales/en.json`

- [ ] Add TypeScript interfaces for research report.
- [ ] Add `research_report?: EventBacktestResearchReport` to `EventBacktestSummary`.
- [ ] Add a Research Mode tab with verdict cards, OOS metrics, candidate strategy table, factor insight table, warnings, and data recommendations.
- [ ] Add bilingual locale keys.

### Task 4: Verification

**Files:**
- No new files beyond above.

- [ ] Run `cd backend && uv run ruff check services/event_contract/backtest_research.py services/event_contract/backtest_helpers.py tests/test_event_contract_backtest.py`.
- [ ] Run `cd backend && uv run pytest tests/test_event_contract_backtest.py tests/test_event_contract_backtest_tasks.py -q`.
- [ ] Run `pnpm build:frontend`.
- [ ] Optionally run a short live backtest or inspect existing JSON to confirm the report shape.
