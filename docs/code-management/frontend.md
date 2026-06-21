# Frontend Code Management

## Scope

This file tracks frontend source files that exceed the 500-line guideline.
The audit excludes `frontend/node_modules/`, `frontend/.next/`, `frontend/dist/`, and generated assets.

## Split Rules

Use short target names by UI domain: `arena/`, `signal/`, `trade/`, `portfolio/`,
`program/`, `analytics/`, `api/`, and `auth/`.

When a component exceeds 500 lines, split state, data loading, view sections, and dialogs.
When a component exceeds 1000 lines, avoid adding new responsibilities before splitting.
Keep hooks in `hooks` or local module files, API clients in `lib`, and visual sections in
small components named after the view they render.

## Priority Areas

P0 files are above 2000 lines and should be split first.
P1 files are above 1000 lines and should not receive unrelated features.
P2 files are above 500 lines and need cleanup during normal work.

## Signal and AI Views

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P0 | 2902 | `frontend/app/components/signal/SignalManager.tsx` | `signal/manager/` |
| P1 | 1876 | `frontend/app/components/hyper-ai/HyperAiPage.tsx` | `ai/page/` |
| P1 | 1063 | `frontend/app/components/signal/AiSignalChatModal.tsx` | `signal/chat/` |
| P2 | 906 | `frontend/app/components/prompt/PromptManager.tsx` | `ai/prompt/` |
| P2 | 885 | `frontend/app/components/prompt/AiPromptChatModal.tsx` | `ai/prompt_chat/` |
| P2 | 659 | `frontend/app/components/klines/AIAnalysisPanel.tsx` | `ai/kline_panel/` |
| P2 | 558 | `frontend/app/components/hyper-ai/HyperAiOnboarding.tsx` | `ai/onboarding/` |
| P2 | 545 | `frontend/app/components/signal/SignalPreviewChart.tsx` | `signal/chart/` |

## Trading and Market Views

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P0 | 2095 | `frontend/app/components/klines/TradingViewChart.tsx` | `trade/chart/` |
| P1 | 1646 | `frontend/app/components/hyperliquid/DashboardInsightView.tsx` | `trade/insights/` |
| P2 | 950 | `frontend/app/components/coinglass/CoinGlassView.tsx` | `trade/coinglass/` |
| P2 | 773 | `frontend/app/components/hyperliquid/HyperliquidAssetChart.tsx` | `trade/asset_chart/` |
| P2 | 747 | `frontend/app/lib/hyperliquidApi.ts` | `api/hyperliquid.ts` |
| P2 | 662 | `frontend/app/components/hyperliquid/OrderForm.tsx` | `trade/order_form/` |
| P2 | 613 | `frontend/app/components/trader/WalletConfigPanel.tsx` | `trade/wallet/` |
| P2 | 557 | `frontend/app/components/klines/KlinesView.tsx` | `trade/klines/` |
| P2 | 553 | `frontend/app/components/trader/BinanceWalletSection.tsx` | `trade/binance_wallet/` |

## Portfolio and Arena Views

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P0 | 2299 | `frontend/app/components/portfolio/AlphaArenaFeed.tsx` | `portfolio/feed/` |
| P2 | 966 | `frontend/app/main.tsx` | `arena/app_shell/` |
| P2 | 962 | `frontend/app/components/arena/SceneEditor.tsx` | `arena/scene/` |
| P2 | 651 | `frontend/app/components/portfolio/AssetCurveWithData.tsx` | `portfolio/asset_curve/` |
| P2 | 611 | `frontend/app/components/portfolio/ArenaAnalyticsFeed.tsx` | `portfolio/analytics_feed/` |
| P2 | 569 | `frontend/app/components/portfolio/StrategyPanel.tsx` | `portfolio/strategy/` |
| P2 | 562 | `frontend/app/components/portfolio/HyperliquidMultiAccountSummary.tsx` | `portfolio/accounts/` |
| P2 | 551 | `frontend/app/components/arena/NewsZone.tsx` | `arena/news/` |
| P2 | 550 | `frontend/app/components/portfolio/TraderDetailModal.tsx` | `portfolio/trader_modal/` |
| P2 | 533 | `frontend/app/components/arena/Workstation.tsx` | `arena/workstation/` |
| P2 | 520 | `frontend/app/components/portfolio/AccountDataView.tsx` | `portfolio/account_data/` |
| P2 | 510 | `frontend/app/components/arena/ArenaAssets.tsx` | `arena/assets/` |

## Program and Analytics Views

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P1 | 1361 | `frontend/app/components/program/BacktestModal.tsx` | `program/backtest/` |
| P1 | 1232 | `frontend/app/components/program/ProgramTrader.tsx` | `program/trader/` |
| P2 | 991 | `frontend/app/components/analytics/TradeReplayModal.tsx` | `analytics/replay/` |
| P2 | 942 | `frontend/app/components/analytics/AttributionAnalysis.tsx` | `analytics/attribution/` |
| P2 | 937 | `frontend/app/components/factor/FactorLibrary.tsx` | `analytics/factor/` |
| P2 | 932 | `frontend/app/components/program/AiProgramChatModal.tsx` | `program/chat/` |
| P2 | 829 | `frontend/app/components/analytics/AiAttributionChatModal.tsx` | `analytics/chat/` |
| P2 | 814 | `frontend/app/components/analytics/PromptBacktest.tsx` | `analytics/prompt_backtest/` |
| P2 | 774 | `frontend/app/components/backtest/BacktestTool.tsx` | `program/backtest_tool/` |

## Shared App and Auth

| Priority | Lines | File | Split Target |
| --- | ---: | --- | --- |
| P1 | 1869 | `frontend/app/lib/api.ts` | `api/clients/` |
| P1 | 1049 | `frontend/app/components/settings/SettingsPage.tsx` | `settings/page/` |
| P2 | 799 | `frontend/app/lib/auth.ts` | `auth/client.ts` |
| P2 | 671 | `frontend/app/components/layout/SettingsDialog.tsx` | `settings/dialog/` |

## Execution Checklist

Split data hooks before JSX sections when possible.
Move modal internals into local child components with typed props.
Keep visual behavior unchanged unless the task explicitly asks for UX changes.
After each split, run the focused frontend command and capture any UI risk in the PR.
