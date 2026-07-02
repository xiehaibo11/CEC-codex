# Professional Backtest Tool Design

## Problem

The current event-contract backtest still exposes a multi-reviewer voting model. Even with a smaller threshold, this encourages the wrong mental model: many AI reviewers vote long, short, or hold, and the trade only exists if enough reviewers agree. A professional trader would not run a trade desk this way. Risk reviewers should not vote for direction; they should veto, downgrade, or explain why a setup is not tradable.

## Goal

Convert the first phase of the Backtest Tool from a voting-first tool into a trader workflow tool while preserving existing API fields and historical compatibility.

## Professional Workflow

The backtest should evaluate each candidate in this order:

1. Signal edge: is there enough directional edge to care?
2. Risk veto: do fake breakout, trap, range-middle, weak volume, MTF conflict, or data issues make this untradable?
3. Execution reality: are costs, slippage, lag, L2 coverage, and CoinGlass coverage realistic enough?
4. Backtest reliability: are sample size, drawdown, market-regime stability, and data coverage strong enough to trust the result?

## Phase 1 Scope

This implementation adds a `professional_v1` decision policy without removing legacy fields.

Backend response additions:

- `decision_policy`: `professional_v1` by default.
- `edge_score`: 0-100 signal quality score.
- `risk_score`: 0-100 risk pressure score.
- `execution_score`: 0-100 execution feasibility score.
- `decision_grade`: A/B/C/D/F.
- `trade_readiness`: `tradable`, `watch`, or `blocked`.
- `veto_reasons`: Chinese list of hard veto reasons.
- `decision_diagnostics`: structured score breakdown for UI/debugging.

Decision behavior:

- Direction still comes from the strongest long/short side.
- Critical risk reviewers no longer create an impossible 30-person unanimity requirement.
- Critical holds become veto reasons.
- A trade is allowed only if edge is strong, risk is controlled, execution is feasible, no veto exists, and score quality passes.
- If a setup has edge but fails risk/execution, it becomes watch or blocked with explicit diagnostics.

Frontend behavior:

- Default saved config should migrate old high vote thresholds to professional defaults.
- Primary UI copy should emphasize professional scoring and risk veto, not 30 AI voting.
- Results should show professional decision readiness and diagnostics near the summary.
- Existing AI decision tables remain available for audit.

## Out of Scope for Phase 1

- Full walk-forward optimizer.
- Monte Carlo simulator.
- Database migration for persisted old result JSON.
- New external data ingestion beyond existing K-line, L2, and CoinGlass paths.
- Live order routing changes.

## Test Strategy

- Add backend regression tests for `professional_v1` allowing a strong edge without 30/30 unanimity.
- Add backend regression tests proving critical risk holds veto the setup.
- Add API/type compatibility by keeping legacy vote fields.
- Run existing event-contract tests and ruff.
- Run frontend build as minimum UI validation.
