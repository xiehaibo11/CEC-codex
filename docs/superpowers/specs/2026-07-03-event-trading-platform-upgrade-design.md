# 事件合约交易平台六模块升级设计

日期：2026-07-03
状态：已获用户批准（全部六项，按序交付）
前置：docs/superpowers/specs/2026-07-02-backtest-tool-credibility-design.md（已完成）

## 背景

回测可信度改造完成后，反转策略（run 850，指纹 `75913e8ca179d8da`，UTC 08-23 时段过滤）
在 33 天训练期首次统计显著（272 笔 61.76%，CI [55.86, 67.34]，p=0.022）。当前验证依赖
人工触发的回放式 holdout；归因只覆盖永续 AI 决策；Dashboard 看不到事件合约活动。
本升级把"验证-交易-展示-归因-信号-因子"闭环产品化。

## 模块 1：事件合约前向实时纸面交易器（核心）

**目标**：把候选策略挂到实时行情上前向模拟下注，数据自动累积，取代人工回放验证。

- 新表 `event_contract_paper_traders`：id, name, enabled, symbol, exchange, environment,
  config(TEXT, 完整策略配置 JSON 含 allowed_utc_hours/platform 等), stake_amount,
  initial_balance, current_balance, strategy_fingerprint, created_at, updated_at。
- 新表 `event_contract_paper_bets`：id, trader_id(FK), direction, status
  (`pending_entry|open|settled`), decision_time, entry_time, entry_price, expiry_time,
  expiry_price, result(`win|loss|draw|NULL`), pnl, stake, payout_ratio, market_state,
  signal_strength, reason(TEXT), analysis_snapshot(TEXT JSON), created_at, updated_at。
  幂等迁移，追加 MIGRATIONS。
- 新服务 `services/event_contract/live_paper_trader.py`：
  - `run_live_paper_cycle()` 由 task_scheduler 每 60 秒调度（注册进
    `services/startup.py::initialize_services`，shutdown 时移除）。
  - 每周期对每个 enabled trader：
    1. **结算阶段**：对 `open` 状态且 `expiry_time` 已过的 bet，取到期时刻所在 1m bar 的
       open 价结算（与回测 open-to-open 口径一致，复用 `_settle_event_contract` 语义含
       refund），写 result/pnl/expiry_price，更新 trader 余额。到期 bar 缺失容忍
       `max_expiry_lag_seconds` 后仍无 → status 保持 open 并告警一次。
    2. **入场确认阶段**：对 `pending_entry` 的 bet，若下一根 1m bar 已开出 → 填
       entry_price = 该 bar open，entry_time = bar 开始时刻，expiry_time = entry_time +
       expiry_minutes*60，status → open。
    3. **决策阶段**：若最新已收盘 1m bar 比该 trader 最后决策 bar 新，且无
       `pending_entry/open` 的 bet（非重叠），且 `_session_allows` 通过 → 调用
       `event_contract_service.predict(db, config)`；`allow_trade` 且方向为 long/short →
       插入 `pending_entry` bet（记录 analysis 快照与 reason）。predict 异常不得中断
       循环，记 system_logger 并继续下一 trader。
- API `api/event_contract_routes.py` 新增（复用现有 router）：
  - `POST /api/event-contract/paper-traders`（body: name, config, stake_amount,
    initial_balance）→ 创建（计算并存 fingerprint）。
  - `GET /api/event-contract/paper-traders` → 列表含实时统计。
  - `PUT /api/event-contract/paper-traders/{id}`（enabled 开关等）。
  - `GET /api/event-contract/paper-traders/{id}/bets?limit=&offset=` → 逐笔。
  - `GET /api/event-contract/paper-traders/{id}/stats` → n/wins/losses/draws、
    decided_win_rate、Wilson CI、p 值 vs 该配置盈亏平衡线、累计 pnl、余额曲线
    （复用 `backtest_stats.wilson_interval/binomial_p_value`）。
- 验收：创建一个 run-850 配置的 trader 后，无人工干预下自动产生决策→下注→结算记录。

## 模块 2：归因分析覆盖事件合约

- `GET /api/analytics/event-contract`：query 支持 trader_id/start/end；返回
  overview（n、decided_win_rate、CI、pnl、fee）+ 按 `direction`、`market_state`、
  `utc_hour_bucket`（0-3/4-7/.../20-23）三维拆解，各桶含 n/win_rate/pnl。数据源
  `event_contract_paper_bets`（settled）。
- `GET /api/analytics/summary` 的 `by_source` 增加 `event_contract` 计数与 net_pnl
  （不改既有键语义）。
- 前端 Attribution Analysis 页新增"事件合约"标签页：维度表格 + 概览卡（EN+ZH）。
- 验收：纸面交易器产生的已结算 bet 在归因页可按三维拆解。

## 模块 3：Dashboard 事件合约面板（跟单视图）

- 新组件 `frontend/app/components/portfolio/EventPaperTraderCard.tsx`（及子目录拆分）：
  - trader 选择（多 trader 下拉）、实时下注流（方向/入场价/倒计时/结算结果，5s 轮询）、
    统计卡（decided_win_rate + Wilson CI 进度条：CI 下界相对 55.56% 盈亏平衡线的位置、
    累计 pnl、余额）。
  - 放入 ComprehensiveView 顶部区域（跟随现有卡片布局），EN+ZH。
- 验收：Dashboard 打开即可实时看到下注与结算（跟单视角）。

## 模块 4：滚动验证自动化

- 新表 `event_contract_validation_log`：id, strategy_fingerprint, source_run_id,
  holdout_run_id, window_start, window_end, decided, wins, created_at。幂等迁移。
- 调度任务（task_scheduler，每 12 小时）：对每个 enabled paper trader 的 fingerprint，
  找到该指纹最近一次 validation_log 的 window_end（无则取其 source run 的 end_time），
  若距今 ≥12h 未验证数据 → 用 holdout 端点同等逻辑创建回测任务（窗口 = 上次 end →
  now-15m），完成后（轮询或完成回调）把 decided/wins 追加 validation_log。
- `GET /api/event-contract/validation/{fingerprint}` → 累计 n/wins、合并 Wilson CI、
  p 值、逐段列表（验证进度：目标 550 笔）。
- 前端 Backtest Tool 可信度卡片下新增"滚动验证进度"折叠区：累计 CI 曲线数据 + 进度条。
- 验收：不再需要人工触发 holdout；进度接口/页面显示累计显著性。

## 模块 5：因子驱动信号池

- 通过现有信号 API 创建（作为种子数据脚本 `backend/scripts/seed_factor_signals.py`，
  幂等：存在同名则跳过）：
  - 信号 `LOG_RETURN_1 反转`（metric `factor:LOG_RETURN_1`，阈值取近 30 天 P5/P95
    分位，方向=反转：低于 P5 看多、高于 P95 看空 → 两条信号定义）。
  - 信号 `DEPTH_RATIO 失衡`（metric `factor:DEPTH_RATIO`，P90 以上看多、P10 以下看空）。
  - 信号池 `因子反转池`（OR 逻辑，symbols=["BTC"], exchange=binance）。
- 若 `factor:` 前缀信号在检测/预测路径缺失或报错，修复该路径（属实现细节，以现有
  `_find_factor_signal_triggers` 与 signal_detection_service 为准）。
- 绑定：把池 ID 写入账户 3 的 `account_strategy_configs.signal_pool_ids`（保留定时触发）。
- 验收：`predict_signal_combination` 对该池给出近 7 天触发频率；池状态在信号页可见。

## 模块 6：衰竭反转自定义因子

- 用表达式引擎注册自定义因子 `EXHAUSTION_REVERSAL`（名称稳定）：表达式基于现有函数库
  （以 `factor_expression/definitions.py` 实际函数名为准）刻画"连续同向后的过度延伸"，
  概念式：`NEG(MUL(ZSCORE_PROXY(ROC(close,3)), VOLUME_CONFIRM))`——实现者按注册表
  选用等价函数（如 ROC、STDDEV、SMA 组合），表达式 ≤500 字符。
- 通过 `/api/factors/evaluate` 计算 BTC 1h/4h 前向 IC/ICIR；把结果（无论好坏）写入
  交付报告；ICIR 绝对值 ≥1 才保存入库（`/api/factors/custom`），否则记录结论不保存。
- 验收：因子库页面可见该因子及其 IC 评分（或报告解释为何不予保存）。

## 全局约束

- 后端测试 `cd backend && uv run pytest`；前端验证 `pnpm build:frontend`；EN+ZH 同加。
- 迁移幂等 + 追加 `MIGRATIONS`；新调度任务必须在 `shutdown_services` 中可停。
- 不触碰实盘下单路径（hyperliquid_*/binance_* 交易客户端）；纸面交易器只写自有新表。
- API 只增不改；新端点跟随现有 auth 依赖模式。
- predict 复用：模块 1 不复制分析逻辑，直接调 `event_contract_service.predict`。
- 每模块独立提交、独立可验收；按 1→6 顺序交付。

## 非目标

- 不做 HIBT/币安事件合约真实下单（验证达标后另立项目）。
- 不做多 symbol 扩展（先 BTC）。
- 不改评审员规则阈值（策略调优与本升级分离）。
