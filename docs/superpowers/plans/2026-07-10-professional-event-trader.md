# 专业多周期事件合约交易员 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有事件合约 Paper Trader 上实现固定 5/10 分钟、trend-follow、多周期专业 AI、严格每日风控和 Paper/Live 执行模式边界。

**Architecture:** 复用 `event_contract_service` 的行情、结算和质量分析，在其上增加一个生产策略守卫和多周期快照；Paper Trader 通过每秒 bar-boundary cycle 执行，使用数据库去重和每日风控；Live 通过 capability-gated adapter 接口，当前没有真实事件合约适配器时明确失败闭锁。

**Tech Stack:** FastAPI、SQLAlchemy/PostgreSQL、APScheduler、pytest、React18/TypeScript/i18next、Vite。

---

## Task 1: 建立失败优先的生产策略契约测试

**Files:**
- Create: `backend/tests/test_event_contract_production_policy.py`
- Modify: `backend/tests/test_event_contract_trend_follow.py`
- Modify: `backend/tests/test_event_contract_config_defaults.py`

- [x] **Step 1: 写失败测试**

覆盖：expiry 只接受 5/10；缺省 signal_mode 是 trend_follow；显式 range_boundary/exhaustion_fade 被生产策略拒绝；Paper Trader 默认 mode 为 paper、leverage 为 10、max_daily_trades 为 10；live 无 adapter 时返回 capability error；生产配置 non-overlap 永远为 true。

- [x] **Step 2: 运行目标测试确认失败**

运行：`uv run --project backend pytest -q backend/tests/test_event_contract_production_policy.py`

预期：新增断言因当前服务仍接受 1/3/15 分钟或旧 signal_mode 而失败。

- [x] **Step 3: 保持测试失败，进入最小实现**

不修改测试以迎合当前行为；下一任务只实现这些契约。

## Task 2: 收紧配置和生产 Trader 守卫

**Files:**
- Modify: `backend/services/event_contract/config.py`
- Modify: `backend/api/event_contract_routes.py`
- Modify: `backend/services/event_contract/paper_trader_api.py`
- Modify: `backend/services/event_contract/analysis.py`
- Test: `backend/tests/test_event_contract_production_policy.py`

- [x] **Step 1: 实现 expiry 和 signal policy**

后端 normalize 层只接受 `{5, 10}`。生产入口缺省注入 `signal_mode="trend_follow"`，显式旧模式直接抛出 ValueError；历史回测读取旧 run 时保留 summary，不修改已保存结果。生产 Trader 创建/启用时强制 `non_overlapping_only=True`。

- [x] **Step 2: 实现最小 Paper Trader 配置默认值**

创建 Trader 时补齐 `execution_mode="paper"`、`leverage=10`、`trade_margin=100`、`max_daily_trades=10`、`profit_target_multiplier=2`、`signal_mode="trend_follow"`。旧生产配置在启用前拒绝，不静默转换其历史 fingerprint。

- [x] **Step 3: 运行契约测试确认通过**

运行：`uv run --project backend pytest -q backend/tests/test_event_contract_production_policy.py backend/tests/test_event_contract_trend_follow.py backend/tests/test_event_contract_config_defaults.py`

## Task 3: 增加 Trader 执行配置与幂等迁移

**Files:**
- Modify: `backend/database/models/event_contract.py`
- Create: `backend/database/migrations/add_event_contract_production_fields.py`
- Modify: `backend/database/migration_manager.py`
- Modify: `backend/services/event_contract/paper_trader_api.py`
- Test: `backend/tests/test_event_paper_models.py`

- [x] **Step 1: 写模型字段失败测试**

断言 `EventContractPaperTrader` 包含 `execution_mode`、`leverage`、`trade_margin`、`max_daily_trades`、`profit_target_multiplier`、`last_decision_time`，默认值分别为 `paper`、10、100、10、2、NULL。

- [x] **Step 2: 实现 ORM 和迁移**

迁移使用 information_schema 检查列后添加，追加到 `MIGRATIONS`；不修改现有 Bet 数据，不启用现有 range Trader。

- [x] **Step 3: 运行模型和迁移相关测试**

运行：`uv run --project backend pytest -q backend/tests/test_event_paper_models.py backend/tests/test_event_paper_seed_static.py`

## Task 4: 增加 4H/30M/15M/10M/5M 多周期快照与专业 AI 分析

**Files:**
- Create: `backend/services/event_contract/multi_timeframe.py`
- Create: `backend/services/event_contract/professional_ai.py`
- Modify: `backend/services/event_contract/analysis.py`
- Modify: `backend/services/event_contract_service.py`
- Modify: `backend/services/event_contract/config.py`
- Test: `backend/tests/test_event_contract_multi_timeframe.py`
- Test: `backend/tests/test_event_contract_professional_ai.py`

- [x] **Step 1: 写失败测试**

测试 1M K 线聚合为 5M、10M、15M、30M、4H 时只使用已完成 bar；缺失高周期样本返回 HOLD；高周期方向冲突返回 HOLD；专业 AI prompt 包含五个周期的 OHLCV/方向摘要和 5/10 expiry。

- [x] **Step 2: 实现纯数据快照 helper**

以已收盘 1M bars 按 UTC 边界聚合，输出每个周期最后一个完整 bar、方向、收益、EMA/RSI/ATR 等最小特征；不读取未来 bar。4H warmup 不足时 fail-closed。

- [x] **Step 3: 实现结构化专业 AI 调用**

复用现有 LLM 配置解析和 HTTP 解析能力，但单独使用生产 prompt；输出只允许 `long|short|hold`、置信度、周期判断、invalid_conditions。AI 失败时返回 HOLD，不生成模拟 AI 结果。

- [x] **Step 4: 将专业 AI 结果接入生产分析**

只有 `trend_follow` 且高周期方向一致、AI 输出方向与规则方向一致、置信度达到配置阈值时才允许交易；结果写入 prediction 和 paper bet snapshot。

- [x] **Step 5: 运行测试**

运行：`uv run --project backend pytest -q backend/tests/test_event_contract_multi_timeframe.py backend/tests/test_event_contract_professional_ai.py`

## Task 5: 实现每秒 bar-boundary Paper Trader cycle 和交易风控

**Files:**
- Modify: `backend/services/event_contract/live_paper_trader.py`
- Modify: `backend/services/startup.py`
- Modify: `backend/services/event_contract/paper_trader_api.py`
- Test: `backend/tests/test_event_paper_trader_cycle.py`
- Test: `backend/tests/test_event_paper_risk_controls.py`

- [x] **Step 1: 写失败测试**

覆盖：同一已收盘 bar 只决策一次；下一根 bar open 填充 pending；存在 open/pending 时不决策；每日第 11 次被拒绝；权益达到 2 倍后停止新单；盈利结算后必须等待新 signal_id；旧 signal_mode Trader 不得继续运行。

- [x] **Step 2: 实现持久化去重**

使用 `last_decision_time` 记录最新已评估 bar 的 close timestamp，即使 AI 返回 HOLD 也不会在每秒循环重复调用。

- [x] **Step 3: 实现 session 风控**

按 Trader 配置时区统计当天 decision bets；在 `_maybe_decide` 前检查 daily cap、open exposure、profit target、validated win-rate gate；所有拒绝记录原因但不创建交易 bet。

- [x] **Step 4: 实现每秒调度**

把事件 Paper Trader job 改为 1 秒，APScheduler 设置 `max_instances=1/coalesce=True/misfire_grace_time=2`。settle/fill/decide 三阶段保持顺序，旧 60 秒语义不再作为生产实时依据。

- [x] **Step 5: 运行 Paper cycle 测试**

运行：`uv run --project backend pytest -q backend/tests/test_event_paper_trader_cycle.py backend/tests/test_event_paper_risk_controls.py`

## Task 6: 增加 Paper/Live 执行路由和能力闭锁

**Files:**
- Create: `backend/services/event_contract/execution.py`
- Modify: `backend/services/event_contract/live_paper_trader.py`
- Modify: `backend/api/event_contract_routes.py`
- Modify: `backend/services/event_contract/paper_trader_api.py`
- Test: `backend/tests/test_event_contract_execution_mode.py`

- [x] **Step 1: 写失败测试**

断言 paper adapter 只写 Paper Bet；live adapter 在没有 capability 时返回明确错误且不调用 Hyperliquid/Binance perpetual order client；execution mode 不能由 AI 输出覆盖。

- [x] **Step 2: 实现 adapter 接口**

定义 `EventExecutionAdapter`、`PaperEventExecutionAdapter` 和 `UnavailableLiveEventExecutionAdapter`。Live 接口预留 `open`、`settle`、`close` capability，但当前返回 `live_event_contract_adapter_unavailable`。

- [x] **Step 3: 增加 API 配置和响应状态**

Paper Trader 创建/更新/列表返回 execution_mode、capability、leverage、trade_margin、daily count、profit target status。Live 选择必须显示能力校验失败原因。

- [x] **Step 4: 运行执行模式测试**

运行：`uv run --project backend pytest -q backend/tests/test_event_contract_execution_mode.py`

## Task 7: 更新前端配置、箭头页和中英文文案

**Files:**
- Modify: `frontend/app/components/backtest/BacktestConfigPanel.tsx`
- Modify: `frontend/app/components/backtest/BacktestTool.tsx`
- Modify: `frontend/app/components/backtest/types.ts`
- Modify: `frontend/app/components/event-arrow/EventArrowChartPage.tsx`
- Modify: `frontend/app/components/event-arrow/EventArrowStatsPanel.tsx`
- Modify: `frontend/app/lib/eventContractApi.ts`
- Modify: `frontend/app/locales/en.json`
- Modify: `frontend/app/locales/zh.json`
- Test: `backend/tests/test_event_paper_dashboard_static.py`

- [x] **Step 1: 写前端静态失败测试**

断言生产 UI 只出现 5m/10m，包含 Paper/Live、10x、100 USDT、10/day、trend-follow 和 Paper Simulation 文案，不出现 range_boundary/exhaustion_fade 生产选择项。

- [x] **Step 2: 更新配置表单和 API 类型**

expiry options 改为 `[5, 10]`；新增 execution mode、leverage、trade margin、daily limit、profit target 状态；Live capability 不可用时禁用提交。

- [x] **Step 3: 更新箭头页**

只显示 enabled 且 trend_follow 的生产 Trader；显示 Paper/Live、5M/10M、`today/10`、AI confidence 和停止原因；保留最近 bet 箭头的非重绘行为。

- [x] **Step 4: 构建和静态测试**

运行：`uv run --project backend pytest -q backend/tests/test_event_paper_dashboard_static.py` 和 `pnpm build:frontend`。

## Task 8: 数据库现状收敛和全量验证

**Files:**
- Create: `backend/scripts/disable_legacy_event_traders.py`
- Create: `backend/tests/test_event_trader_policy_seed_static.py`
- Modify: `docs/code-management/backend.md`（仅补充策略/执行边界）

- [x] **Step 1: 写脚本静态测试**

断言脚本只禁用显式旧策略 Trader，不删除 bet、不改历史 run、不自动启用 trend Trader。

- [x] **Step 2: 实现一次性收敛脚本**

脚本输出被禁用 Trader 名称和原因；默认 dry-run，必须传 `--apply` 才写库。当前不自动执行真实网或自动启用账户。

- [x] **Step 3: 全量验证**

运行：`uv run --project backend pytest -q`、`pnpm build:frontend`、`python3 scripts/code_split_audit.py`，并检查 `/api/health`、Paper Trader API 和前端生产资源。

## 执行规则

- 每个任务先写测试并验证 RED，再写最小实现；测试失败时不修改测试来掩盖问题。
- 不清理现有工作区变更；只编辑本计划列出的文件。
- 不提交或执行真实订单；Live capability 适配器另立任务。
- 完成前必须重新检查 `git status --short --branch`，并报告既有变更与本次新增变更的边界。
