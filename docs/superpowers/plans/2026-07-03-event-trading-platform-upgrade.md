# 事件合约交易平台六模块升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 事件合约前向纸面交易器 + 归因/Dashboard/滚动验证/信号/因子五个配套模块，产品化"验证-交易-展示-归因"闭环。

**Architecture:** 后端新增 `services/event_contract/live_paper_trader.py` 与三张新表，复用 `event_contract_service.predict` 与 `backtest_stats`；调度经 `task_scheduler`；前端在 Attribution/Dashboard/Backtest Tool 加卡片。全部 API 只增不改。

**Tech Stack:** FastAPI/SQLAlchemy/pytest（`cd backend && uv run pytest`）；React18/TS/i18next（`pnpm build:frontend`）。

**Spec:** `docs/superpowers/specs/2026-07-03-event-trading-platform-upgrade-design.md`（实现者必读，本计划只写接口与验收，实现细节以 spec + 现有代码模式为准）

## Global Constraints

- 迁移幂等（information_schema 检查）并追加到 `backend/database/migration_manager.py` 的 `MIGRATIONS` 末尾。
- 新调度任务在 `services/startup.py::initialize_services` 注册、`shutdown_services` 停止。
- 不触碰 hyperliquid_*/binance_* 实盘交易客户端；纸面交易器只写自有新表。
- 前端新文案 EN+ZH 同加（`frontend/app/locales/{en,zh}.json` 的既有分组内）。
- 每任务：先写失败测试（TDD），实现，回归，单独 commit（简短祈使句消息）。
- predict 复用：不复制分析逻辑，调用 `event_contract_service.predict(db, config)`。
- 统计复用：`services/event_contract/backtest_stats.py` 的 `wilson_interval/binomial_p_value`。

---

### Task 1: 纸面交易器数据层（表 + ORM + 迁移）

**Files:**
- Modify: `backend/database/models/event_contract.py`
- Create: `backend/database/migrations/add_event_contract_paper_tables.py`
- Modify: `backend/database/migration_manager.py`
- Test: `backend/tests/test_event_paper_models.py`

**Interfaces (Produces):**
- ORM `EventContractPaperTrader`（表 `event_contract_paper_traders`）字段见 spec 模块 1。
- ORM `EventContractPaperBet`（表 `event_contract_paper_bets`）字段见 spec；`status` 取值 `pending_entry|open|settled`；`trader_id` FK ondelete CASCADE；索引：trader_id、status、decision_time。
- 幂等迁移 `upgrade()`（CREATE TABLE IF NOT EXISTS 风格或 information_schema 检查），追加 MIGRATIONS 末尾。

- [ ] 失败测试：断言两个 ORM 的 `__table__.columns` 覆盖 spec 字段集合；迁移 `upgrade()` 可重复执行两次无异常（模式参考 `backend/tests/test_event_contract_trade_log_schema.py` 与 `add_event_contract_trade_log_ai_columns.py`）。
- [ ] 实现 ORM + 迁移 + 注册。
- [ ] `uv run pytest tests/test_event_paper_models.py tests/test_event_contract_trade_log_schema.py -q` 通过。
- [ ] Commit: `Add event contract paper trader tables`

### Task 2: 实时纸面交易循环服务

**Files:**
- Create: `backend/services/event_contract/live_paper_trader.py`
- Modify: `backend/services/startup.py`（注册 60s interval task `EVENT_PAPER_TRADER_JOB_ID = "event_paper_trader_cycle"`；shutdown 移除）
- Test: `backend/tests/test_event_paper_trader_cycle.py`

**Interfaces:**
- Consumes: Task 1 的两个 ORM；`event_contract_service.predict`；`_session_allows`（service mixin）；1m K 线读取沿用 `event_contract_service._load_klines` 或直接查 `crypto_klines`。
- Produces:

```python
def run_live_paper_cycle(now_ts: Optional[int] = None, db: Optional[Session] = None) -> Dict[str, int]:
    """One cycle over all enabled traders. Returns counters:
    {"settled": x, "entries_filled": y, "decisions": z, "bets_opened": w, "errors": e}.
    Injectable now_ts/db for tests."""
```

- 周期三阶段（结算→入场确认→决策）语义严格按 spec 模块 1；决策非重叠：存在 `pending_entry|open` bet 时跳过决策；predict 异常 → system_logger 记 ERROR、errors 计数、继续。
- 决策去重：trader 上最后一笔 bet 的 decision_time 所在 bar 不重复决策（无 bet 时用 trader 级 last_decision 字段或最近 bet 查询，二选一，写清）。

- [ ] 失败测试（monkeypatch predict 返回固定 allow_trade 决策 + sqlite 内存库建两表）：
  (a) 首周期开出 pending_entry bet；(b) 下一根 bar 出现后 entry 填充为该 bar open；
  (c) 到期后按到期 bar open 结算 win/loss/pnl 且余额更新；(d) 有未结 bet 时不再决策；
  (e) predict 抛异常时循环不中断且 errors+1。
- [ ] 实现 + 注册调度。
- [ ] `uv run pytest tests/test_event_paper_trader_cycle.py -q` 通过；全量回归通过。
- [ ] Commit: `Add live event-contract paper trading cycle`

### Task 3: 纸面交易器 API + 统计

**Files:**
- Modify: `backend/api/event_contract_routes.py`
- Test: `backend/tests/test_event_paper_trader_api.py`

**Interfaces (Produces):** spec 模块 1 的五个端点。stats 返回：

```json
{"trader_id":1,"n_settled":0,"decided":0,"wins":0,"losses":0,"draws":0,
 "decided_win_rate":0,"win_rate_ci_low":0,"win_rate_ci_high":0,
 "p_value_vs_breakeven":1.0,"break_even_win_rate":55.56,
 "total_pnl":0,"current_balance":10000,"stake_amount":100,
 "open_bets":0,"strategy_fingerprint":"..."}
```

创建端点用 `_normalize_config` 校验 config 并算 `_strategy_fingerprint` 存库。

- [ ] 失败测试：服务层函数级测试（建 sqlite、插 trader+bets，断言 stats 数学与 wilson 一致；创建函数对非法 config 抛 ValueError）。路由薄壳不强制 TestClient。
- [ ] 实现。
- [ ] 回归 + Commit: `Add event paper trader API with credibility stats`

### Task 4: 部署首个交易器 + 端到端验证

**Files:**
- Create: `backend/scripts/seed_event_paper_trader.py`（幂等：同名跳过）
- Test: `backend/tests/test_event_paper_seed_static.py`（脚本存在性/幂等结构静态断言）

**Interfaces:** 种子配置 = run 850 公开配置（从 `event_contract_backtest_runs.config WHERE id=850` 读出，剔除 start_time/end_time/reviewer_weights），name `Reversal-08-23-UTC`，stake 100，initial 10000。
**手动验证（实现者执行并写入报告）**：运行脚本 → 触发一次 `run_live_paper_cycle()`（真实 DB）→ 展示 trader 行与（若市场给出信号）bet 行；无信号时展示 decisions 计数增加即可。
- [ ] Commit: `Seed first live event paper trader from run 850 config`

### Task 5: 归因分析后端扩展

**Files:**
- Modify: `backend/api/analytics_routes.py`（新端点 `/api/analytics/event-contract`；`summary` 的 `by_source` 加 `event_contract`）
- Test: `backend/tests/test_analytics_event_contract.py`

**Interfaces (Produces):** spec 模块 2 的响应结构；utc_hour_bucket 键形如 `"h00-03"`。只读 `event_contract_paper_bets`（status=settled）。
- [ ] 失败测试：sqlite 插入已知 bets，断言三维拆解数字与 overview CI。
- [ ] 实现（注意 analytics_routes.py 2000+ 行——新逻辑放独立 helper 模块 `backend/api/analytics_event_contract.py`，路由文件只加薄壳）。
- [ ] 回归 + Commit: `Add event contract dimension to attribution analytics`

### Task 6: 归因前端标签页

**Files:**
- Modify: `frontend/app/components/analytics/AttributionAnalysis.tsx`（加"事件合约"Tab，薄壳）
- Create: `frontend/app/components/analytics/attribution-analysis/EventContractTab.tsx`
- Modify: `frontend/app/lib/eventContractApi.ts` 或 analytics API 模块（fetch 函数 + 类型）
- Modify: locales en/zh
- Test: `pnpm build:frontend`

**Interfaces:** Consumes Task 5 端点。UI：概览卡（decided/win_rate/CI/pnl）+ 三个维度表。
- [ ] 实现 + build 通过 + Commit: `Show event contract attribution tab`

### Task 7: Dashboard 跟单面板

**Files:**
- Create: `frontend/app/components/portfolio/EventPaperTraderCard.tsx`（>300 行则拆 `event-paper-trader/` 子目录）
- Modify: `frontend/app/components/portfolio/ComprehensiveView.tsx`（顶部渲染）
- Modify: `frontend/app/lib/eventContractApi.ts`（traders/bets/stats fetch + 类型）
- Modify: locales en/zh
- Test: `pnpm build:frontend` + 更新 `backend/tests/test_backtest_tool_credibility_static.py` 同风格新建 `backend/tests/test_event_paper_dashboard_static.py`

**Interfaces:** 5s 轮询 bets（limit 20）+ stats；倒计时用 expiry_time-now；CI 进度条以 55.56 为基准线。
- [ ] 实现 + build + 静态测试 + Commit: `Add live event paper trader card to dashboard`

### Task 8: 滚动验证自动化后端

**Files:**
- Create: `backend/database/migrations/add_event_contract_validation_log.py`（+ ORM 入 `database/models/event_contract.py`，+ MIGRATIONS）
- Create: `backend/services/event_contract/rolling_validation.py`
- Modify: `backend/services/startup.py`（12h interval task，可停）
- Modify: `backend/api/event_contract_routes.py`（`GET /api/event-contract/validation/{fingerprint}`）
- Test: `backend/tests/test_rolling_validation.py`

**Interfaces (Produces):**

```python
def run_rolling_validation_cycle(now_ts=None, db=None) -> Dict[str, int]  # {"launched": n, "recorded": m}
def cumulative_validation_stats(db, fingerprint) -> dict  # {"n","wins","ci_low","ci_high","p_value","segments":[...]}
```

窗口推进与记录语义按 spec 模块 4；holdout 复用现有 create_event_backtest_task（config 取自 fingerprint 对应最新 run 的 config，同 holdout 端点逻辑）。
- [ ] 失败测试：伪造 validation_log 行断言 cumulative 数学；cycle 的窗口推进逻辑（monkeypatch task 创建）。
- [ ] 实现 + 回归 + Commit: `Automate rolling out-of-sample validation`

### Task 9: 滚动验证前端进度区

**Files:**
- Modify: `frontend/app/components/backtest/CredibilityCard.tsx`（或其下新增折叠区组件）
- Modify: `frontend/app/lib/eventContractApi.ts`；locales en/zh
- Test: `pnpm build:frontend`

**Interfaces:** Consumes Task 8 端点（以 summary.strategy_fingerprint 查询）；显示累计 n/550 进度、合并 CI、分段列表。
- [ ] 实现 + build + Commit: `Show rolling validation progress in credibility card`

### Task 10: 因子驱动信号池种子

**Files:**
- Create: `backend/scripts/seed_factor_signals.py`（幂等）
- Test: `backend/tests/test_seed_factor_signals.py`（对脚本的构造函数级测试：阈值来自分位数、重复运行不重复建）

**Interfaces:** 按 spec 模块 5：4 条 factor: 信号 + OR 池 + 绑定账户 3 的 signal_pool_ids（保留 scheduled_trigger_enabled）。阈值：查 `factor_values` 近 30 天 LOG_RETURN_1 的 P5/P95、DEPTH_RATIO 的 P10/P90（SQL percentile_cont）。若 `factor:` 信号在 `signal_detection_service`/`ai_signal_generation_tool_prediction` 路径不可用，修复并在报告中说明改动。
**手动验证**：运行脚本，调 `predict_signal_combination`（或等价预测工具函数）输出近 7 天触发次数写入报告。
- [ ] Commit: `Seed factor-driven reversal signal pool`

### Task 11: 衰竭反转自定义因子

**Files:**
- Create: `backend/scripts/register_exhaustion_factor.py`
- Test: 报告内附 IC/ICIR 数字（无单测要求；表达式合法性由 `/api/factors/validate-expression` 等价服务函数验证）

**Interfaces:** 按 spec 模块 6：先读 `backend/services/factor_expression/definitions.py` 确认可用函数名，构造 ≤500 字符表达式；用 factor 评估服务算 BTC 1h+4h IC/ICIR；|ICIR|≥1 才保存（名称 `EXHAUSTION_REVERSAL`）。结论无论好坏写入报告与 commit 消息。
- [ ] Commit: `Register exhaustion reversal custom factor`（或 `Evaluate exhaustion reversal factor (not saved: ICIR x.xx)`）

### Task 12: 全量回归 + 收尾

- [ ] `cd backend && uv run pytest -q` 全绿；`pnpm build:frontend` 通过。
- [ ] 更新 `.superpowers/sdd/progress.md`。
- [ ] Commit（若有零散修正）。

## Self-Review

- Spec 覆盖：模块 1→Task 1-4；模块 2→Task 5-6；模块 3→Task 7；模块 4→Task 8-9；模块 5→Task 10；模块 6→Task 11。
- 占位符：无 TBD；实现细节授权给实现者但接口/语义/验收明确。
- 类型一致：`run_live_paper_cycle`/`cumulative_validation_stats` 签名在消费任务中未被引用（互相独立）；前端 fetch 函数命名由 Task 6/7/9 内自洽。
