# Backtest Validation Layer Design

## Problem

The Backtest Tool now has a professional decision policy, but the result still focuses on trade summary and a compact quality gate. The quant-book notes that a backtest is not useful unless it proves credibility against look-ahead risk, overfitting, execution-cost optimism, regime instability, and live-performance decay.

## Goal

Add a validation layer to the event-contract backtest result so the user can answer: "Can this backtest be trusted after sample splitting, randomized stress, market-regime breakdown, and conservative live decay?"

## Scope

This phase adds a deterministic `validation_report` to the existing backtest summary. It does not rerun the strategy with trained parameters and does not place orders. It analyzes the trades already produced by the backtest engine.

## Report Sections

1. `walk_forward`
   - Split settled trades chronologically into rolling windows.
   - Report each window's trades, win rate, PnL, max drawdown, and pass/fail.
   - Summarize pass rate, worst-window win rate, worst-window PnL, and stability score.

2. `monte_carlo`
   - Deterministically reshuffle realized trade PnLs using a fixed seed.
   - Report profitable-ratio, p5/p50/p95 PnL, and p95 max drawdown.
   - This tests sequence risk without changing settlement math.

3. `regime_stability`
   - Group trades by existing `market_state`.
   - Report win rate, PnL, trade count, and drawdown by regime.
   - Identify weakest regime and unstable regime count.

4. `live_decay_estimate`
   - Apply quant-book-style conservative decay: base 50%, plus penalties for zero/weak cost assumptions, partial runs, weak sample size, and unstable regimes.
   - Report conservative PnL and verdict.

## UI

Add a compact "可信度验证 / Validation" panel under Quality Gate showing:

- Walk-forward pass rate and worst window.
- Monte Carlo profitable ratio and p5 PnL.
- Weakest regime and unstable count.
- Live-decay conservative PnL and verdict.

## Compatibility

- Keep all existing summary fields.
- If there are too few trades, report warnings rather than failing the API.
- Persist the new summary JSON automatically through the existing backtest run persistence.

## Tests

- Unit-test report creation from synthetic trade lists.
- Assert stable trades pass walk-forward and Monte Carlo.
- Assert weak regime and decay warnings are surfaced.
- Run existing event-contract tests.
