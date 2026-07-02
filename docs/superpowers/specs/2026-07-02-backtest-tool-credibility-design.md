# Backtest Tool（5 分钟事件合约）可信度改造设计

日期：2026-07-02
状态：已获用户批准（方案 A：分阶段完整改造）
目标：把 Backtest Tool 的回测结果做到"专业可信"，验证策略真实胜率后再考虑实盘。
实盘目标平台：HIBT（hibt.com）、币安事件合约、其他 CEX 类似产品（做成平台预设）。

## 背景与审计结论

Backtest Tool 页面（`frontend/app/components/backtest/`）是 5 分钟事件合约（押注涨跌，
赢得 `stake × payout`，输掉 `stake`）的预测 + 历史回测工具，后端引擎在
`backend/services/event_contract/`。专业审计确认：核心盈亏数学、盈亏平衡线
（payout=0.8 时 55.56%）、K 线特征管线（无前视偏差）均正确；但存在以下会使
回测胜率虚高的问题：

1. **评审员学习权重时间泄漏（最严重）**：`reviewer_learning.py:173-188` 的
   `fit_reviewer_stats` 读取 `event_contract_trade_logs ORDER BY id DESC LIMIT 1500`，
   无任何时间过滤；回测方向由该权重倾斜（`analysis.py:40-62` weighted_direction），
   且每次回测结束后 `clear_reviewer_cache()`（`backtest.py:480-486`）导致下次重跑
   用"刚写入的同窗口结果"重新拟合——评审员相当于考前看过答案。
2. **成交假设过于理想**：默认 `fee_rate=0, slippage_bps=0, delay_seconds=0`，
   且入场价 = 决策 K 线自身收盘价（`backtest.py:401`）——看到价格的同一瞬间以
   该价格成交，现实不可能。
3. **平台规则不匹配**：真实平台以自家价格指数/标记价格结算（HIBT 锚定现货指数；
   币安用 Price Index），回测用数据源 K 线收盘价；币安平局退还本金，回测默认平局
   算输；HIBT 赔付 80–85%、无手续费、最低 3U、有开单频率限制。
4. **统计缺陷**：`target_win_rate_met` 在 `target_min_trades=10` 的小样本上即可判
   "达标"，无置信区间与显著性检验；1 分钟一决策、5 分钟一结算导致相邻交易窗口
   高度重叠（样本不独立），现有 i.i.d. 蒙特卡洛高估可信度；预测概率从未与实际
   结果校准。
5. **确定性 bug**：`config.py:58-61` 用 `X or default` 使显式 0 值被吃掉；
   `data.py:411-419` 写入的 9 列在 `database/models/event_contract.py` 的
   `EventContractTradeLog` ORM 上不存在（模型漂移，潜在 500）。
6. **过拟合面**：约 35 个可调开关 + 代码中硬编码的经验阈值（如
   `analysis.py:178-180` 注明"88.8–88.9 是经验亏损点"）。现有 walk-forward/OOS
   仅是已实现交易流的描述性切分，检测不到线下手工调参。

平台规则来源：
- HIBT：结算价取周期结束时锚定现货指数的公开标记价格；赢赚 80–85%；无手续费；
  最低 3U；单标的持仓上限与每分钟开单次数限制（support.hibt.com 及公开报道）。
- 币安事件合约：权利金模式，固定赔付；平局（结算=入场）退还权利金；最低 5 USDT；
  无额外手续费；单日最大亏损 10,000 USDT（binance.com 官方 FAQ）。

## 总体方案

分四个独立可验收阶段：P0 修错误 → P1 执行现实化 + 平台预设 → P2 统计可信层 →
P3 页面改造。API 响应字段只增不改，保持旧前端兼容。

## P0：修正确定性错误（后端引擎）

### P0.1 评审员权重时间隔离
- `fit_reviewer_stats` / `compute_reviewer_weights` 增加 `before_ts` 参数；回测路径
  传 `config.start_time`，只用回测窗口开始之前的成绩单拟合权重。
- 新增配置 `reviewer_weights_mode`：
  - `pre_window`（默认）：只用窗口前数据；
  - `static`：只用 `reviewer_expertise.py` 内置基础权重（完全确定性）；
  - `unsafe_legacy`：保留现行为，仅供对比实验，结果中带警告标记。
- 回测结果记录所用模式与权重快照哈希；回测结束不再触发全局缓存清除+重拟合的
  泄漏循环（缓存按 `before_ts` 分键）。

### P0.2 行权基准价（strike）改为决策后第一个可观测价格
- `delay_seconds` 默认 0 → 3；strike = 决策时刻 + delay 后第一根 K 线的**开盘价**
  （当前实现取延迟后 bar 的 close，改为 open）；找不到符合延迟容忍的 bar 仍跳过
  并计数（沿用 `entry_delay_skipped_count`）。
- 结算时间基准同步：`expiry_ts = strike_bar_open_ts + expiry_min*60`（保持现有
  `_resolve_expiry_index` 容忍逻辑）。

### P0.3 滑点语义澄清
- `slippage_bps` 重新定义并文档化为"受理时刻基准价的不利漂移"（保留其改变输赢
  判定基准的行为——现实中基准价变了判定线就是变了），与手续费（只影响盈亏额）
  严格区分。UI 与 API 描述同步更新。

### P0.4 小 bug 修复
- `config.py` 中 payout/fee/slippage/delay 改为 `is not None` 判空（对齐
  `target_win_rate` 的已有写法），显式 0 不再被默认值覆盖。
- `EventContractTradeLog` ORM 补齐 `consensus_source, ai_participated, ai_model,
  ai_account_name, signal_time, signal_type, event_signal,
  entry_delay_lag_seconds, expiry_lag_seconds` 列；新增幂等迁移（先查列存在性），
  追加到 `migration_manager.MIGRATIONS`。

## P1：平台预设 + 保守默认（后端 + 前端）

### P1.1 平台预设
后端 `event_contract/platforms.py` 定义预设常量；前端配置面板加平台选择器，
选中即填充参数（仍可手动微调，微调后标记为"自定义"）：

| 预设 | payout | 平局 | fee | 最小注 | 特殊规则 |
|---|---|---|---|---|---|
| `hibt` | 0.80（可调 0.80–0.85） | loss（保守；官方细则确认后可改） | 0 | 3 USDT | `min_seconds_between_trades`（开单频率限制） |
| `binance_event` | 0.80 | **refund**（退还本金，pnl = -fee） | 0 | 5 USDT | `daily_loss_cap=10000`，当日亏损触及即停止开新仓 |
| `custom` | 手动 | loss/refund/win 可选 | 手动 | 手动 | 无 |

- 引擎新增 `draw_result="refund"` 结算分支（现有 draw/loss 之外）。
- 回测配置与结果均持久化 `platform` 字段，保证可复现。
- 盈亏平衡线随预设动态计算并返回（平局退款时以非平局样本计）。

### P1.2 结算敏感度分析（新指标）
- 对每笔已结算交易，计算若结算价偏移 ±2/±5/±10 bps 输赢是否翻转；输出
  `settlement_sensitivity: {bps_2: x%, bps_5: y%, bps_10: z%}`（翻转比例）。
- 用途：真实平台以自家指数结算，与回测 K 线源存在偏差；靠 1–2 bps 微弱优势赢的
  策略实盘会退化为抛硬币。翻转比例高 → 优势脆弱，可信度卡片降级。

### P1.3 非重叠下注模式（默认开启）
- `non_overlapping_only=true`（默认）：上一笔未结算前不产生新决策；关闭可作对比。
- 同时实现 `min_seconds_between_trades`（HIBT 频率限制）与
  `daily_loss_cap`（币安规则）两个可选约束。

## P2：统计可信层（后端指标 + 校准）

### P2.1 置信区间与显著性
- 胜率输出 Wilson 95% 置信区间；
- 单侧二项检验：胜率 vs 平台盈亏平衡线，输出 p 值；
- `target_win_rate_met` 重定义：**CI 下界 ≥ 盈亏平衡线** 且点估计 ≥ target 才为
  true；样本不足时返回 `insufficient_sample` 状态而非 false。

### P2.2 蒙特卡洛升级
- 重叠模式下改用移动块自助法（block bootstrap，块长 ≥ expiry_window/interval 根）；
  非重叠模式保留 i.i.d.；固定种子可复现（沿用现有 200 次、p5/p50/p95 输出格式）。

### P2.3 概率校准
- 按预测概率分桶（如 55–65/65–75/75–85/85+）统计实际胜率，输出可靠性表 +
  Brier 分数；样本 <50 时返回 `insufficient_sample`。

### P2.4 参数指纹 + 一键样本外验证
- 每次回测计算并存储配置哈希（除时间窗口外的全部参数）；
- 新端点/按钮"冻结参数验证"：用同一哈希配置在用户选定的更晚窗口重跑，
  返回两次结果并排对比（含 CI 是否重叠、样本外是否仍过盈亏平衡线）。

## P3：页面改造（frontend/app/components/backtest/）

- 结果面板以保守口径为主，顶部新增**可信度卡片**：
  样本量红绿灯（<30 红 / 30–100 黄 / >100 绿）、Wilson CI、显著性徽章、
  结算敏感度、校准表（够样本时）。
- 平台预设选择器（HIBT / 币安事件合约 / 自定义），显示该平台平局规则与动态
  盈亏平衡线。
- "达标"徽章逻辑改为 P2.1 的严格定义；旧的 `target_win_rate_met` 展示移除。
- 所有新文案 EN + ZH 同时加入 `frontend/app/locales/`；沿用现组件拆分模式
  （新子组件放 `backtest/` 下，必要时建 kebab-case 子目录）。
- 预测面板（PredictionPanel）沿用平台预设参数，不做其他改动。

## 错误处理

- 平台预设加载失败/未知平台 → 回退 `custom` 并提示；
- 敏感度/校准/CI 计算对空交易列表返回空对象而非报错；
- 冻结参数验证的目标窗口数据不足 → 明确报"数据不足"，不静默缩窗；
- 迁移全部幂等（列存在性检查），启动不因迁移失败阻塞（遵循仓库迁移规则）。

## 测试

后端（`backend/tests/`，pytest）：
- 评审员权重 `before_ts` 过滤：窗口内/后的 trade log 不参与拟合；
- payout/fee/slippage/delay 显式 0 生效；
- `draw_result="refund"` 结算：pnl = -fee，不计入胜负样本；
- strike = 延迟后第一根 bar 开盘价；延迟超容忍跳过计数；
- 结算敏感度翻转计数的确定性用例；
- Wilson CI 与二项检验的已知值用例；块自助法种子化可复现；
- 非重叠模式：结算前无新交易；daily_loss_cap 触发停止；
- 新迁移幂等性（重复执行无异常）。

前端：
- `pnpm build:frontend` 通过；
- 更新 `test_backtest_tool_task_ui_static.py` 等拆分感知静态测试，覆盖平台
  选择器与可信度卡片的关键不变量。

## 实施顺序与验收

P0 → P1 → P2 → P3，每阶段独立提交、独立可验收：
- P0 验收：同参数重复回测结果完全一致（评审员权重不再随运行漂移）；
- P1 验收：切换平台预设产生正确的结算/约束差异，敏感度指标输出；
- P2 验收：小样本不再"达标"，CI/显著性/校准字段齐备；
- P3 验收：页面双语展示可信度卡片，构建通过。

## 非目标（本期不做）

- 不改动 Program Trader / Prompt 回测（`backend/backtest/` 引擎）；
- 不做自动参数优化/参数搜索（现阶段只会加剧过拟合）;
- 不接入 HIBT/币安事件合约真实下单 API（验证通过后另立项目）；
- 不清理 `analysis.py`/`features.py` 中既有硬编码阈值（仅通过样本外验证暴露
  其过拟合程度，改阈值属策略调优，另行处理）。
