# AI量化交易从0到1 —— 学习资料目录

来源：https://waylandz.com/quant-book/

本目录用于存放从该站点拉取的量化交易教程内容，供 CEC-codex 项目（多智能体 AI 永续合约交易平台）研发时参考，尤其是 Part 4（多智能体系统）与回测/风控/执行相关章节，和本项目的 Hyper AI 多智能体架构、event_contract 回测引擎有较强的对照价值。

已拉取的内容见本目录下的 markdown 文件；尚未拉取的用原站链接标注，需要时可再单独拉取。

## Part 1 - 快速体验

- [Part 1 概述](/quant-book/Part1概述/)
- [x] [第01课：量化交易全景图](./01-量化交易全景图.md)

## Part 2 - 量化基础

- [ ] [Part 2 概述](/quant-book/Part2概述/)
- [ ] [第02课：金融市场与交易基础](/quant-book/第02课：金融市场与交易基础/)
- [ ] [第03课：数学与统计基础](/quant-book/第03课：数学与统计基础/)
- [ ] [第04课：技术指标的真实角色](/quant-book/第04课：技术指标的真实角色/)
- [ ] [第05课：经典策略范式](/quant-book/第05课：经典策略范式/)
- [ ] [第06课：数据工程的残酷现实](/quant-book/第06课：数据工程的残酷现实/)
- [x] [第07课：回测系统的陷阱](./07-回测系统的陷阱.md)（摘要版）— 与咱们 `backend/services/event_contract/backtest.py` 直接相关
- [ ] [第08课：Beta、对冲与市场中性](/quant-book/第08课：Beta、对冲与市场中性/)

## Part 3 - 机器学习

- [ ] [Part 3 概述](/quant-book/Part3概述/)
- [ ] [第09课：监督学习在量化中的应用](/quant-book/第09课：监督学习在量化中的应用/)
- [ ] [第10课：从模型到Agent](/quant-book/第10课：从模型到Agent/)

## Part 4 - 多智能体系统（与 Hyper AI 架构最相关）

- [x] [Part 4 概述](./Part4-概述.md)
- [x] [第11课：为什么需要多智能体](./11-为什么需要多智能体.md)
- [x] [第12课：市场状态识别](./12-市场状态识别.md) — 对照 `services/market_regime_*`
- [x] [第13课：Regime误判与系统性崩溃模式](./13-Regime误判与系统性崩溃模式.md)
- [x] [第14课：LLM在量化中的应用](./14-LLM在量化中的应用.md) — 对照 `services/hyper_ai_service/`、`ai_decision_service/`
- [x] [第15课：风险控制与资金管理](./15-风险控制与资金管理.md)（摘要版）— 对照交易安全规则（AGENTS.md）
- [x] [第16课：组合构建与风险暴露管理](./16-组合构建与风险暴露管理.md)（摘要版）
- [x] [第17课：在线学习与策略进化](./17-在线学习与策略进化.md)（摘要版）— 对照 `services/event_contract/reviewer_learning.py`（贝叶斯评审员权重学习）

## Part 5 - 生产与实战

- [ ] [Part 5 概述](/quant-book/Part5概述/)
- [ ] [第18课：交易成本建模与可交易性](/quant-book/第18课：交易成本建模与可交易性/)
- [ ] [第19课：执行系统 - 从信号到真实成交](/quant-book/第19课：执行系统%20-%20%E4%BB%8E%E4%BF%A1%E5%8F%B7%E5%88%B0%E7%9C%9F%E5%AE%9E%E6%88%90%E4%BA%A4/) — 对照 `backend/backtest/execution_simulator.py`
- [ ] [第20课：生产运维](/quant-book/第20课：生产运维/)
- [ ] [第21课：项目实战](/quant-book/第21课：项目实战/)
- [ ] [第22课：总结与进阶方向](/quant-book/第22课：总结与进阶方向/)

## 附录

- [ ] [附录A：实盘交易记录标准指南](/quant-book/附录A：实盘交易记录标准指南/)
- [ ] [附录B：量化系统的12种典型死亡方式](/quant-book/附录B：量化系统的12种典型死亡方式/)
- [ ] [附录C：人类决策与自动化边界](/quant-book/附录C：人类决策与自动化边界/)
- [ ] [附录D：量化交易常见问题FAQ](/quant-book/附录D：量化交易常见问题FAQ/)

## 资源

- [ ] [资源索引](/quant-book/Resources/)
- [ ] [数据提供商对比](/quant-book/数据提供商对比/)
- [ ] [券商的平台和API](/quant-book/券商的平台和API/)
- [ ] [头部量化机构案例](/quant-book/头部量化机构案例/)
- [ ] [Tick、L-2级盘口数据购买渠道](/quant-book/Tick、L-2级盘口数据购买渠道/)
- [ ] [HFT机房](/quant-book/HFT机房/)
- [ ] [FIX协议入门](/quant-book/FIX协议入门/)
- [ ] [市场数据授权入门](/quant-book/市场数据授权入门/)
- [ ] [ArXiv Papers](/quant-book/ArXiv Papers/)

> 上面未拉取的链接是相对路径，完整地址为 `https://waylandz.com` + 该路径。
