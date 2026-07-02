# Professional Backtest Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the event-contract Backtest Tool into a professional trading-desk workbench by removing the shared-AI-vote workflow from professional mode, expiring stale tasks, and making prediction/backtest outputs explain direction, action, risk, execution, and independent AI trader results clearly.

**Architecture:** Backend professional mode always routes through deterministic professional workflow plus 30 independent AI trader research, never through blocking LLM consensus. Task reads mark old running tasks expired so stale ai_review rows cannot keep the UI stuck. Frontend separates direction bias from trade action/readiness and hides legacy consensus controls for professional workflow.

**Tech Stack:** FastAPI/Python, pytest, React/TypeScript, i18next, Vite.

---

### Task 1: Backend stale task expiry

**Files:**
- Modify: `backend/services/event_contract/tasks.py`
- Modify: `backend/tests/test_event_contract_backtest_tasks.py`

- [x] Add tests that create/update a stale running `event_contract_backtest_tasks` row and assert reads return `status="failed"`, `phase="expired"`, and a clear expired message.
- [x] Implement expiry helper in `tasks.py` for `pending/running/pause_requested` rows whose `updated_at` is older than 10 minutes.
- [x] Call expiry helper in `get_event_backtest_task` and `find_latest_event_backtest_task` before returning rows.
- [x] Verify the new tests fail before implementation and pass after implementation.

### Task 2: Professional mode disables blocking AI consensus

**Files:**
- Modify: `backend/services/event_contract/config.py`
- Modify: `backend/tests/test_event_contract_backtest.py`

- [x] Add a test that `_normalize_config({decision_policy:"professional_v1", consensus_mode:"ai_confirmed"})` returns `consensus_mode="rule_only"`.
- [x] Add a test that legacy mode still preserves `ai_confirmed`.
- [x] Implement the config normalization rule.
- [x] Verify the tests fail before implementation and pass after implementation.

### Task 3: Frontend professional prediction clarity

**Files:**
- Modify: `frontend/app/components/backtest/PredictionPanel.tsx`
- Modify: `frontend/app/components/backtest/BacktestConfigPanel.tsx`
- Modify: `frontend/app/components/backtest/BacktestResultsPanel.tsx`
- Modify: `frontend/app/locales/zh.json`
- Modify: `frontend/app/locales/en.json`

- [x] Replace the top prediction badge with trade action/readiness rather than raw final direction.
- [x] Add cards for `方向倾向`, `交易动作`, `阻断原因`, and `下一步条件`.
- [x] Rename or hide consensus controls when `decision_policy="professional_v1"`; show them only for legacy comparison.
- [x] Change stale/expired task UI text to explain it is not running.
- [x] Add Chinese and English locale strings.

### Task 4: Verification and live checks

- [x] Run backend ruff on touched backend files.
- [x] Run event-contract pytest suite.
- [x] Run `pnpm build:frontend`.
- [x] Sync `frontend/dist/` to `backend/static/`.
- [x] Query `/api/event-contract/backtest/tasks/latest` and verify stale task is no longer shown as running.
- [x] Query `/api/event-contract/predict` with professional + `ai_confirmed` payload and verify the backend returns `consensus_mode="rule_only"`.
