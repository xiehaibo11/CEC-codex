# Professional Backtest Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a professional trader workflow decision layer to the event-contract Backtest Tool so it uses signal edge, risk veto, and execution feasibility instead of exposing 30-AI voting as the primary decision model.

**Architecture:** Add `professional_v1` as the default decision policy in backend config and compute professional diagnostics inside `EventContractAnalysisMixin`. Preserve legacy vote fields, then surface new diagnostics in prediction/trade/backtest responses and frontend summary panels.

**Tech Stack:** FastAPI/Pydantic, Python event-contract services, pytest, ruff, React/Vite/TypeScript, i18next.

---

### Task 1: Backend professional decision policy tests

**Files:**
- Modify: `backend/tests/test_event_contract_backtest.py`

- [ ] Add a test where 8 long reviewer decisions out of a 25-reviewer panel produce a tradable professional setup when features are clean and no risk veto exists.
- [ ] Add a test where the same signal is blocked when a critical risk reviewer holds.
- [ ] Run the two new tests and confirm they fail before production code changes.

### Task 2: Backend professional decision scoring

**Files:**
- Modify: `backend/services/event_contract/config.py`
- Modify: `backend/services/event_contract/analysis.py`
- Modify: `backend/services/event_contract/signal.py`
- Modify: `backend/services/event_contract/backtest.py`
- Modify: `backend/api/event_contract_routes.py`

- [ ] Add `decision_policy` to normalized config, defaulting to `professional_v1`.
- [ ] Add professional scoring helper methods to compute edge, risk, execution, grade, readiness, and veto reasons.
- [ ] Use professional readiness for allow/watch/block decisions while preserving legacy consensus fields.
- [ ] Include diagnostics in prediction, event signal, trade logs, and AI consensus payloads.
- [ ] Extend API request models with optional `decision_policy`.
- [ ] Run backend tests and ruff.

### Task 3: Frontend types and default config

**Files:**
- Modify: `frontend/app/lib/eventContractApi.ts`
- Modify: `frontend/app/components/backtest/types.ts`
- Modify: `frontend/app/components/backtest/BacktestTool.tsx`

- [ ] Add professional diagnostics fields to TypeScript interfaces.
- [ ] Add `decision_policy` to form state and request payloads.
- [ ] Default to `professional_v1` and migrate legacy high-threshold saved configs.

### Task 4: Frontend professional result display

**Files:**
- Modify: `frontend/app/components/backtest/BacktestResultsPanel.tsx`
- Modify: `frontend/app/components/backtest/PredictionPanel.tsx`
- Modify: `frontend/app/components/backtest/BacktestConfigPanel.tsx`
- Modify: `frontend/app/locales/en.json`
- Modify: `frontend/app/locales/zh.json`

- [ ] Add a compact professional diagnostics panel to prediction/results.
- [ ] Reword config copy to explain signal edge, risk veto, execution feasibility.
- [ ] Keep legacy reviewer details as audit information.
- [ ] Add bilingual locale keys.
- [ ] Run frontend build.

### Task 5: End-to-end verification

**Files:**
- Runtime only.

- [ ] Run `cd backend && uv run pytest tests/test_event_contract_backtest.py tests/test_event_contract_backtest_tasks.py -q`.
- [ ] Run targeted `ruff check` on changed backend files.
- [ ] Run `pnpm build:frontend`.
- [ ] Verify `/api/health` and a direct Python smoke sample showing professional diagnostics.
