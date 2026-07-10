# 专业多周期事件合约交易员设计

日期：2026-07-10
状态：已获用户批准，进入实现

## 目标

在现有事件合约 Paper Trader 基础上，增加一个面向生产的专业 AI 交易员：使用 4H、30M、15M、10M、5M 多周期分析，支持做多/做空，固定 5M/10M 到期，单持仓、每日最多 10 次、75% 目标胜率、权益翻倍后停止当日交易，并允许在 Paper 与 Live 模式之间选择。

## 重要边界

- `paper` 使用真实或指定环境的行情做价格模拟，不发送真实订单；前端必须显示 Paper Simulation。
- `live` 只允许在具体事件合约平台适配器报告 capability 后执行。当前仓库只有永续合约交易客户端，没有完整的 HIBT/Binance Event Contract 下单适配器，因此未接入前 Live 请求必须失败闭锁，不能退化成永续下单。
- 10x 杠杆属于永续/保证金产品概念；固定赔率二元事件合约如果平台没有杠杆字段，只记录配置语义，不伪造杠杆或提前平仓能力。
- 历史回测结果保留；生产 Paper Trader 不得使用 `range_boundary`、`exhaustion_fade` 或其他反向策略。

## 策略

周期职责：

- 4H：大趋势和市场状态；
- 30M：中期方向一致性；
- 15M：结构、支撑阻力、趋势延续；
- 10M：主要 setup；
- 5M：最终收盘触发与 5/10 分钟合约方向。

多头必须满足高周期方向不冲突、10M setup 有效、5M 收盘确认；空头使用镜像规则。任一高周期冲突、数据不足、AI 置信度不足、风险门阻断，都输出 HOLD。生产配置固定 `signal_mode=trend_follow`。

专业分析 AI 只输出结构化分析，不直接改变金额或杠杆；Decision 层将分析转换为 long/short/hold，代码风控最终决定是否允许执行。

## 执行和风控

- `expiry_minutes` 仅允许 5 或 10；
- `leverage` 默认 10，并由代码固定上限校验；
- `trade_margin` 默认 100 USDT，账户资金独立配置；
- 一个 Trader 同时最多一个 `pending_entry/open` 合约；
- 每个本地交易日最多 10 次新开仓；
- 当前合约结算后必须等待新的已确认信号，不复用同一 signal_id；
- 目标胜率 75% 作为质量门，不作为收益保证；历史/OOS 样本不足或目标不达标时阻止生产开仓；
- 达到 `session_start_equity * 2` 后停止当日新开仓；固定到期产品不能提前平仓时等待现有合约结算，支持提前关闭的平台才调用 close capability；
- 实时循环每秒检查 bar 边界，使用持久化 `last_decision_time` 去重；下一根 1M bar 出现时填充入场价，避免 60 秒轮询造成整分钟延迟。

## 数据和持久化

Paper Trader 增加 execution_mode、leverage、trade_margin、max_daily_trades、profit_target_multiplier、last_decision_time 等字段；迁移必须幂等。交易计数按配置时区查询已创建 bet，权益翻倍基准使用 Trader 的 initial_balance 或持久化 session baseline。

## 前端

生产配置页提供：5M/10M、Paper/Live、主网/测试网行情环境、杠杆、单笔金额、每日次数和翻倍目标。Live 不具备平台 capability 时展示阻断原因，不显示可执行状态。事件箭头页只展示生产 trend_follow Trader，并显示当前执行模式、周期、当日次数和停止原因。

## 验收标准

1. API 和前端拒绝 1/3/15/其他 expiry；
2. 创建或启用生产 Trader 时缺省策略自动变成 trend_follow，显式 range_boundary/exhaustion_fade 被拒绝；
3. 4H/30M/15M/10M/5M 方向快照进入 AI prompt 和 bet analysis_snapshot；
4. 单持仓、每日 10 次、75%质量门、权益翻倍停止均有失败优先测试；
5. 同一已收盘 bar 不重复调用 AI，下一根 bar open 可填充 pending entry；
6. Paper/Live API/UI 状态一致，未注册 Live adapter 时永不发送订单；
7. 后端相关测试、全量测试和前端构建通过。
