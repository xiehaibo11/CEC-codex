# TradingAgents 风格多智能体审查层设计

日期：2026-07-08  
项目：CEC-codex  
参考项目：`TradingAgents/`  
状态：设计草案，未进入实现

## 1. 背景

CEC-codex 当前已经有 AI Trader、信号系统、回测工具、亏损归因、风控拦截、Binance 和 Hyperliquid 执行路径。现有问题不是简单地“AI 判断错了”，而是下单前缺少一个把信号质量、回测有效性、市场状态、近期亏损归因和执行风险统一审查的中间层。

TradingAgents 的价值不在于直接复制其投资策略，而在于它把交易决策拆成多角色流程：分析师、正反方研究员、交易员、风险辩论员、组合经理。CEC-codex 可以借鉴这种流程，但必须保留自己的实盘安全边界：信号验证、回测验证、风控硬规则和交易所执行器仍然是最终约束。

本设计目标是在现有 AI 下单链路和确定性执行风控之间增加一个轻量多智能体审查层。

## 2. 核心原则

1. 审查层不直接下单，只能批准、降级、拦截或要求测试网观察。
2. AI 的提示词只做解释和辅助判断，不能替代信号验证和执行层硬规则。
3. 主网只允许经过验证的信号驱动新增仓位。
4. 测试网可以承担样本收集职责，但必须记录审查结果和后续盈亏。
5. 平仓、减仓、降低风险的动作默认优先放行，但仍需记录审查报告。
6. 审查输出必须结构化，可回测、可追踪、可复盘。
7. TradingAgents 作为流程参考，不作为外部依赖直接嵌入第一版。

## 3. 插入位置

现有链路：

```text
AI 生成下单决策
  -> 执行层风控
  -> Binance / Hyperliquid / Paper 执行
```

目标链路：

```text
AI 生成下单决策
  -> Multi-Agent Review 审查层
  -> 信号验证门 / 风控硬规则
  -> Binance / Hyperliquid / Paper 执行
```

审查层应接收 AI 原始决策、账户状态、触发上下文、信号上下文、回测摘要、近期亏损归因、市场状态和当前持仓。审查层输出统一 verdict，执行层根据 verdict 调整或拒绝订单。

## 4. 与 TradingAgents 的对应关系

| TradingAgents 角色 | CEC-codex 互补角色 | 说明 |
| --- | --- | --- |
| Market / Technical Analyst | Regime Reviewer | 审查市场状态、趋势、波动、CVD、OI、taker ratio、RSI 等是否支持方向。 |
| Sentiment / News Analyst | Context Reviewer | 新闻只能作为辅助证据，不能单独驱动开仓。 |
| Bull Researcher | Bull Reviewer | 只允许基于结构化证据支持执行。 |
| Bear Researcher | Bear Reviewer | 专门查找信号不足、亏损重复、逆势和风控缺陷。 |
| Trader Agent | AI Trader 原决策 | CEC-codex 已有 AI Trader 决策生成，不需要重复实现。 |
| Risk Debators | Risk Committee | 判断是否缩仓、降杠杆、测试网观察或阻断。 |
| Portfolio Manager | Execution Judge | 统一裁决 approve / reduce_size / hold / block / testnet_only。 |
| Decision Memory | Review + Loss Memory | 使用 AIDecisionLog、亏损归因和审查记录形成反馈闭环。 |

## 5. 推荐方案

第一版采用轻量 Python Orchestrator，而不是直接引入 LangGraph。

原因：

- CEC-codex 已经有 FastAPI、SQLAlchemy、交易执行器和风控模块。
- 第一版目标是实盘安全和可验证，不是展示复杂 agent 图。
- 普通 service 更容易测试、回滚、接入现有执行路径。
- 文件边界更清晰，后续仍可增加 LangGraph adapter。

推荐目录结构：

```text
backend/services/ai_review/
  __init__.py
  schemas.py
  context_builder.py
  orchestrator.py
  agents/
    signal_reviewer.py
    backtest_reviewer.py
    regime_reviewer.py
    loss_reviewer.py
    bull_reviewer.py
    bear_reviewer.py
    risk_committee.py
    execution_judge.py
  persistence.py
```

第一阶段只实现最小闭环：

```text
Signal Reviewer
Backtest Reviewer
Loss Reviewer
Execution Judge
```

第二阶段再加：

```text
Regime Reviewer
Bull / Bear Debate
Risk Committee
```

## 6. ReviewContext 输入模型

审查层的输入应是单笔决策的完整证据包。

建议字段：

```json
{
  "account_id": 1,
  "account_name": "AI Trader",
  "exchange": "binance",
  "environment": "testnet",
  "symbol": "BTC",
  "operation": "buy",
  "target_portion_of_balance": 0.2,
  "leverage": 3,
  "decision_reason": "...",
  "decision_snapshot": {},
  "trigger_context": {},
  "signal_snapshot": {},
  "backtest_summary": {},
  "recent_loss_summary": {},
  "market_regime": {},
  "positions": [],
  "portfolio": {},
  "prices": {},
  "now": "2026-07-08T00:00:00Z"
}
```

关键要求：

- `trigger_context` 必须包含 signal id、pool id、metric、threshold、actual value、time window。
- `signal_snapshot` 必须结构化，不应从 AI reason 文本里解析。
- `backtest_summary` 必须标明样本量、手续费、滑点、样本外状态和是否通过最小样本门槛。
- `recent_loss_summary` 来自亏损归因服务，用于识别重复错误。

## 7. Agent 输出模型

每个 reviewer 输出统一结构：

```json
{
  "agent_role": "signal_reviewer",
  "verdict": "pass | warn | block | testnet_only",
  "confidence": 0.82,
  "evidence": [
    {
      "kind": "signal_forward_record",
      "id": "DEPTH_RATIO",
      "summary": "样本 35，胜率 57%，净收益为正"
    }
  ],
  "warnings": [],
  "blocking_reasons": [],
  "recommended_adjustments": {
    "max_target_portion": 0.2,
    "max_leverage": 3
  },
  "report_text": "..."
}
```

最终裁判输出：

```json
{
  "verdict": "approve | reduce_size | hold | block | testnet_only",
  "symbol": "BTC",
  "operation": "buy",
  "max_target_portion": 0.2,
  "max_leverage": 3,
  "blocking_reasons": [],
  "required_evidence": [],
  "summary": "信号通过验证，但近期同方向亏损，允许测试网小仓位执行"
}
```

## 8. 各 Reviewer 设计

### 8.1 Signal Reviewer

职责：判断信号是否有资格驱动订单。

检查项：

- 是否为 signal trigger。
- signal id / metric 是否存在。
- 样本量是否达到最低阈值。
- 前向净盈亏是否为正。
- 分层读数是否存在极端亏损区间。
- AI 方向是否和信号方向一致。

输出策略：

- 主网样本不足：`block` 或 `testnet_only`。
- 测试网样本不足：`testnet_only`，允许观察。
- 信号净亏损：`block`。
- 信号通过但极端档样本不足：`warn` 并降低仓位。

### 8.2 Backtest Reviewer

职责：判断当前规则或信号是否经过可信回测。

检查项：

- 是否存在对应回测记录。
- 是否计入手续费和滑点。
- 是否通过最小样本门槛。
- 是否使用样本外或前进式验证。
- 是否存在未来函数风险。
- prompt backtest 是否和实盘风控一致。

输出策略：

- 无回测：主网阻断，测试网允许观察。
- 回测样本不足：`testnet_only`。
- 回测净亏损：`block`。
- 回测盈利但未计滑点：`warn`，降低仓位或要求重跑。

### 8.3 Loss Reviewer

职责：从亏损单里提取“不要重复犯”的规则。

检查项：

- 最近同 symbol / 同方向是否连亏。
- 是否重复同一新闻叙事。
- 是否在亏损持仓上加仓。
- 亏损归因中是否存在高频标签，如 `stacking_add`、`counter_trend_short`、`unvalidated_signal`。
- 反事实回放是否显示半仓、延迟、宽止损能显著改善结果。

输出策略：

- 连亏方向：`block` 或 `hold`。
- 亏损持仓加仓：`block`。
- 常见亏损标签命中：`warn` 或 `reduce_size`。
- 无足够亏损数据：`pass`，但注明样本不足。

### 8.4 Regime Reviewer

第二阶段实现。

职责：判断当前市场状态是否适合执行。

检查项：

- 当前 1m / 5m / 15m / 1h / 4h regime。
- 是否突破、吸收、诱多、诱空、噪声或趋势延续。
- AI 决策是否逆 4h 趋势。
- 价格行为是否和新闻叙事矛盾。

输出策略：

- regime 为 noise 且信号弱：`hold`。
- 明确逆势且无强信号：`block`。
- 高波动但方向一致：降低仓位。

### 8.5 Bull / Bear Debate

第二阶段实现。

职责：仿 TradingAgents 的正反方辩论，但限制为结构化证据辩论。

规则：

- Bull 只能引用 signal、backtest、regime、portfolio 中的证据。
- Bear 只能引用 loss、risk、sample insufficiency、contradiction 中的证据。
- 双方都不能引用未给定外部信息。
- 辩论结果只作为 Execution Judge 输入，不直接决定执行。

### 8.6 Risk Committee

第二阶段实现。

角色：

- Aggressive Reviewer：是否允许测试网继续积累样本。
- Neutral Reviewer：是否缩仓、降杠杆、加条件执行。
- Conservative Reviewer：是否阻断或 hold。

输出聚合后交给 Execution Judge。

### 8.7 Execution Judge

职责：统一裁决，不允许扩大风险。

硬规则：

- 任一 reviewer 返回 `block` 且理由属于 hard block，最终必须 block。
- 主网 signal 样本不足，最终必须 block 或 testnet_only。
- `reduce_size` 只能降低 AI 原始仓位和杠杆，不能提高。
- `close` / 减仓类动作优先放行。
- 审查层异常时，新增仓位默认 block，平仓默认放行。

## 9. 持久化设计

新增表建议：

```text
ai_review_runs
- id
- account_id
- decision_log_id
- exchange
- environment
- symbol
- operation
- original_target_portion
- original_leverage
- verdict
- final_target_portion
- final_leverage
- final_reason
- latency_ms
- created_at

ai_review_agent_reports
- id
- review_run_id
- agent_role
- verdict
- confidence
- report_json
- report_text
- created_at
```

可选增强 `AIDecisionLog`：

```text
review_run_id
review_verdict
review_blocked_reason
```

如果暂时不改表，也必须把审查结果写进 `decision_snapshot` 的非下划线字段，避免被持久化过滤掉。

## 10. 执行路径接入

建议在 AI 决策生成后、交易所执行前接入：

```python
review = review_ai_decision(db, account, decision, portfolio, positions, prices, trigger_context)

if review.verdict == "block":
    persist_decision_as_not_executed(review)
    return

if review.verdict == "hold":
    decision["operation"] = "hold"

if review.verdict == "reduce_size":
    decision["target_portion_of_balance"] = min(
        decision["target_portion_of_balance"], review.max_target_portion
    )
    decision["leverage"] = min(decision["leverage"], review.max_leverage)

continue_to_existing_risk_guards_and_execution()
```

接入点：

- Binance：`backend/services/trading_commands/binance_execution.py`
- Hyperliquid：`backend/services/trading_commands/hyperliquid_execution.py`
- Paper：可先只记录 review，不阻断，用于训练和验证。

## 11. 主网、测试网、纸面交易策略

### 主网

- 未验证信号：阻断。
- 样本不足：阻断或 testnet_only。
- 连亏方向：阻断。
- 亏损持仓加仓：阻断。
- 审查异常：新增仓位阻断。

### 测试网

- 样本不足可执行，但标记 `validation_mode`。
- 极端读数样本不足时降低仓位。
- 所有结果必须进入审查记录，用于后续信号验证。

### Paper

- 默认不阻断，只记录审查 verdict。
- 用于观察如果启用审查层会改变多少决策。

## 12. API 和前端展示

后端 API：`GET /api/ai-review/runs`、`GET /api/ai-review/runs/{id}`、`GET /api/ai-review/summary`、`POST /api/ai-review/replay-decision/{decision_id}`。

前端建议在现有分析页面增加：

- 审查结论：approve / reduce_size / hold / block / testnet_only。
- 各 reviewer 卡片：Signal、Backtest、Loss、Regime、Risk。
- 阻断原因。
- 仓位/杠杆调整前后对比。
- 与最终实际执行状态对比。

## 13. 测试计划

单元测试：

- Signal Reviewer 样本不足时主网阻断。
- Signal Reviewer 测试网样本不足时 testnet_only。
- Backtest Reviewer 未计滑点时 warn。
- Loss Reviewer 连亏方向 block。
- Execution Judge 不允许扩大 AI 原始仓位。
- 审查服务异常时新增仓位 fail closed。

集成测试：

- Binance 执行路径被审查层阻断时不调用交易所 client。
- Hyperliquid 执行路径同样接入审查层。
- Paper 模式只记录不阻断。
- 审查结果能持久化并在 analytics API 返回。

回归测试：

- 现有风险 guard 仍然生效。
- 现有 signal validation gate 不被绕过。
- AI decision self-consistency 不被移除。
- `hold` / `close` 行为不被错误阻断。

## 14. MVP 范围

第一版只做：`ai_review.schemas`、`ai_review.context_builder`、`SignalReviewer`、`BacktestReviewer`、`LossReviewer`、`ExecutionJudge`、Binance + Hyperliquid 执行路径接入、审查结果持久化、后端只读 API、单元测试和关键集成测试。

暂不做：

- 完整 LangGraph 编排。
- UI 大改版。
- 自动修改策略参数。
- 让审查层直接调用交易所。
- 自动上线规则补丁。

## 15. 后续扩展

第二版：

- Regime Reviewer。
- Bull / Bear Debate。
- Risk Committee。
- prompt backtest 自动 replay。
- 审查结果前端可视化。

第三版：

- LangGraph-compatible adapter。
- 审查 checkpoint / resume。
- 亏损归因自动生成规则候选。
- 规则候选自动发起回测验证。
- 通过验证后进入人工确认或配置开关。

## 16. 验收标准

MVP 完成后，应满足：

1. 主网新增仓位不会由未验证信号直接驱动。
2. 连亏方向会被审查层或现有风控拦截。
3. 亏损持仓加仓会被拦截。
4. 审查结果能持久化，并能追溯每个 reviewer 的理由。
5. 审查层只能降低风险，不能放大风险。
6. Binance 和 Hyperliquid 路径行为一致。
7. 相关测试通过，且不破坏现有 AI decision、prompt backtest、risk guard 测试。

## 17. 推荐实施顺序

1. 先实现 schemas 和 context builder。
2. 实现 deterministic reviewers，不先接 LLM。
3. 实现 execution judge 的硬规则聚合。
4. 接入 Binance testnet 路径。
5. 接入 Hyperliquid 路径。
6. 持久化审查结果。
7. 增加 API。
8. 跑测试和回测。
9. 再考虑引入 Bull / Bear / Risk LLM 审查。

