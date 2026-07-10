# Backend Code Management

## Scope

This file tracks backend source files that exceed the 500-line guideline.
The audit excludes `backend/.venv/`, `backend/static/`, caches, and generated assets.

## Split Rules

Use small modules with clear ownership. Prefer these short target names:
`ai/`, `api/`, `data/`, `trade/`, `factor/`, and `ops/`.

When a file exceeds 500 lines, split by responsibility before adding features.
When a file exceeds 1000 lines, treat the next change as a split opportunity.
Keep route files thin: parse input, call services, and return schemas.
Keep service files focused on one domain workflow.

## Priority Areas

P0 files are above 2000 lines and should be split first.
P1 files are above 1000 lines and should not receive unrelated features.
P2 files are above 500 lines and need ownership cleanup during normal work.

## AI Modules

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P0 | 3945 | `backend/services/hyper_ai_tools.py` | `ai/tools/` |
| P0 | 3570 | `backend/services/ai_decision_service.py` | `ai/decision.py` |
| P0 | 2331 | `backend/services/ai_program_service.py` | `ai/program.py` |
| P0 | 2094 | `backend/services/ai_signal_generation_service.py` | `ai/signal.py` |
| P0 | 2021 | `backend/services/hyper_ai_service.py` | `ai/core.py` |
| P1 | 1229 | `backend/services/ai_prompt_generation_service.py` | `ai/prompt.py` |
| P1 | 1150 | `backend/services/ai_attribution_service.py` | `ai/attribution.py` |
| P2 | 925 | `backend/services/ai_context_compression_service.py` | `ai/context.py` |
| P2 | 655 | `backend/services/ai_prompt_shared_tools.py` | `ai/prompt_tools.py` |
| P2 | 615 | `backend/services/kline_ai_analysis_service.py` | `ai/kline.py` |
| P2 | 578 | `backend/api/hyper_ai_routes.py` | `api/hyper_ai/` |
| P2 | 550 | `backend/services/hyper_ai_memory_service.py` | `ai/memory.py` |
| P2 | 536 | `backend/services/hyper_ai_subagents.py` | `ai/subagents.py` |
| P2 | 524 | `backend/services/hyper_ai_harness.py` | `ai/harness.py` |

## Trading Modules

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P0 | 3556 | `backend/services/hyperliquid_trading_client.py` | `trade/hyperliquid/` |
| P1 | 1769 | `backend/api/hyperliquid_routes.py` | `api/hyperliquid/` |
| P1 | 1756 | `backend/services/trading_commands.py` | `trade/commands.py` |
| P1 | 1579 | `backend/services/binance_trading_client.py` | `trade/binance/` |
| P1 | 1005 | `backend/api/binance_routes.py` | `api/binance/` |
| P2 | 730 | `backend/services/hyperliquid_market_data.py` | `trade/market_data.py` |
| P2 | 579 | `backend/services/hyperliquid_environment.py` | `trade/env.py` |
| P2 | 534 | `backend/api/trader_data_routes.py` | `api/trader_data/` |
| P2 | 508 | `backend/services/trading_strategy.py` | `trade/strategy.py` |

## API Modules

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P0 | 2499 | `backend/routes/program_routes.py` | `api/program/` |
| P0 | 2051 | `backend/api/analytics_routes.py` | `api/analytics/` |
| P0 | 2028 | `backend/api/arena_routes.py` | `api/arena/` |
| P1 | 1649 | `backend/api/account_routes.py` | `api/account/` |
| P1 | 1120 | `backend/api/signal_routes.py` | `api/signal/` |
| P1 | 1085 | `backend/api/ws.py` | `api/ws/` |
| P1 | 1081 | `backend/main.py` | `api/app.py` |
| P2 | 971 | `backend/api/prompt_routes.py` | `api/prompt/` |
| P2 | 737 | `backend/api/coinglass_routes.py` | `api/coinglass/` |
| P2 | 717 | `backend/api/bot_routes.py` | `api/bot/` |
| P2 | 683 | `backend/api/factor_routes.py` | `api/factor/` |
| P2 | 649 | `backend/api/market_flow_routes.py` | `api/market_flow/` |

## Data, Backtest, and Factor Modules

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P0 | 2759 | `backend/services/signal_backtest_service.py` | `data/backtest/` |
| P1 | 1833 | `backend/database/models.py` | `data/models/` |
| P1 | 1324 | `backend/services/signal_detection_service.py` | `factor/signal.py` |
| P2 | 985 | `backend/services/market_flow_collector.py` | `data/market_flow.py` |
| P2 | 913 | `backend/services/market_flow_indicators.py` | `factor/market_flow.py` |
| P2 | 870 | `backend/services/factor_effectiveness_service.py` | `factor/effect.py` |
| P2 | 779 | `backend/services/signal_analysis_service.py` | `factor/analysis.py` |
| P2 | 771 | `backend/backtest/historical_data_provider.py` | `data/history.py` |
| P2 | 757 | `backend/backtest/engine.py` | `data/backtest_engine.py` |
| P2 | 707 | `backend/services/market_regime_service.py` | `factor/regime.py` |
| P2 | 696 | `backend/backtest/execution_simulator.py` | `data/simulator.py` |
| P2 | 648 | `backend/program_trader/data_provider.py` | `data/program.py` |
| P2 | 525 | `backend/services/factor_expression_engine.py` | `factor/expression.py` |
| P2 | 514 | `backend/services/asset_curve_calculator.py` | `data/asset_curve.py` |

## Execution Checklist

Before splitting, add or preserve tests around the affected endpoint or service.
Move pure helpers first, then clients, then orchestration code.
Keep imports acyclic and avoid moving runtime configuration into feature modules.
After each split, run the smallest relevant backend command and record it in the PR.

## Production Event-Contract Boundary

- New production event-contract configurations pass through `services/event_contract/production_policy.py`.
- Production expiry is limited to 5 or 10 minutes, the base feed is 1m, and the signal mode is `trend_follow`.
- `range_boundary` and `exhaustion_fade` remain readable for historical audit only and cannot be enabled for production Paper Trader cycles.
- The production decision stack uses completed 1m bars aggregated into 4h/30m/15m/10m/5m snapshots, then applies the structured professional-AI confirmation gate.
- `execution_mode=paper` uses the local matcher; `execution_mode=live` is capability-gated and must fail closed until a venue-specific event-contract adapter exists. It must never fall through to perpetual order clients.
- Paper Trader cadence is a 1-second scheduler tick with `last_decision_time` idempotency; settlement/fill/decision phases remain ordered and no overlapping contract is opened.
- Fixed risk defaults are 10x, 100 USDT, 10 entries per local day, and stop-new-entry at 2x initial equity. Run `backend/scripts/disable_legacy_event_traders.py` as a dry-run first; `--apply` is required to persist legacy-row disables.
