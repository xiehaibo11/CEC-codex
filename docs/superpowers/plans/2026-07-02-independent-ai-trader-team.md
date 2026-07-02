# Independent AI Trader Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mental model of “30 AI vote together” with “30 professional AI traders trade independently and are ranked by their own backtest results”.

**Architecture:** Add a backend `ai_trader_team` report built during event-contract backtests. The main strategy settlement remains unchanged, but every decision bar also records each of the 30 rule AI traders' own long/short/hold decision and settles that trader independently. The finalized team report is attached to `summary.research_report.ai_trader_team` and shown in the Backtest Tool Research tab.

**Tech Stack:** Python service helper, pytest, React/TypeScript, i18next, Vite.

---

### Task 1: Failing backend test

**Files:**
- Modify: `backend/tests/test_event_contract_backtest.py`

- [x] Add a test importing `build_ai_trader_team_state`, `record_ai_trader_team_decisions`, and `finalize_ai_trader_team_report`.
- [x] Assert the report has `mode="independent_traders"`, `total_traders=30`, separate per-trader metrics, and no consensus vote field.
- [x] Run the test and confirm it fails because the module does not exist yet.

### Task 2: Backend helper and backtest integration

**Files:**
- Create: `backend/services/event_contract/ai_trader_team.py`
- Modify: `backend/services/event_contract/backtest.py`
- Modify: `backend/services/event_contract/backtest_helpers.py`

- [x] Implement team state, record, and finalize helpers.
- [x] In `run_backtest`, compute all 30 rule decisions per decision bar using `reviewer_panel_size=31`, settle each AI trader independently, and attach the report to the summary.
- [x] Keep this independent team report separate from main strategy trades.

### Task 3: Frontend display

**Files:**
- Modify: `frontend/app/lib/eventContractApi.ts`
- Modify: `frontend/app/components/backtest/BacktestResultsPanel.tsx`
- Modify: `frontend/app/locales/zh.json`
- Modify: `frontend/app/locales/en.json`

- [x] Add API types for `ai_trader_team`.
- [x] Show a “30 AI交易员” table inside Research Mode with trader name, strategy type, trade count, win rate, OOS win rate, PnL, max drawdown, overfit risk, and recommendation.

### Task 4: Verification

- [x] Run backend ruff on touched backend files.
- [x] Run event-contract pytest suite.
- [x] Run frontend build.
- [x] Run a real backtest and assert `research_report.ai_trader_team.total_traders == 30`.
