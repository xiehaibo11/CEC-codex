CoinGlass Skills Hub（AI Agent 集成）
CoinGlass API 现已支持通过 CoinGlass Skills Hub 进行 AI Agent 集成。

CoinGlass Skills Hub 是一个开放的技能市场，使 AI Agent 能够通过结构化、可复用的技能包访问 CoinGlass 的专业级加密市场数据与分析能力。

通过 Skills Hub，AI Agent 可以：

访问覆盖合约、现货、期权、ETF 和链上市场的统一实时与历史数据
获取高级数据集，例如资金费率、未平仓量、爆仓数据、L2/L3 订单簿深度、订单流、鲸鱼活动以及宏观指标
自动将自然语言请求映射到正确的 CoinGlass API 接口
无需手动集成 API，即可生成结构化分析结果
快速开始
访问 CoinGlass Skills Hub 仓库：

https://github.com/coinglass-official/coinglass-api-skills

在你的 Agent 环境中安装：

Bash

npx skills add https://github.com/coinglass-official/coinglass-api-skills
安装 Skills（通过 GitHub 下载 ZIP）
点击右上角的 Code 按钮，选择 Download ZIP。

将解压后的文件上传到对应的平台或工具中。

按照对应平台或工具的说明完成后续配置与安装。

Cursor Skills 安装指南： https://cursor.com/docs/skills

Claude Skills 安装指南： https://support.claude.com/en/articles/12512180-use-skills-in-claude

何时使用 Skills Hub
在以下场景中，建议使用 CoinGlass Skills Hub：

构建 AI Agent 或 Copilot
将 CoinGlass 数据集成到基于 LLM 的工作流中
开发交易助手或分析机器人
希望快速完成集成，而无需处理底层 API 调用逻辑
如需直接进行 API 集成，请继续使用下方文档中的各个接口。


搭配 MCP 使用
建议将此 SKILL 与 CoinGlass MCP Service 一起使用：

SKILL：负责理解数据结构、指标含义与分析逻辑
MCP：负责实际接口调用、数据查询与返回结果
两者结合后，可显著提升 AI 在 CoinGlass 数据场景下的理解能力、查询效率与分析准确性。


支持的数据类型
衍生品
市场数据
持仓量
资金费率
多空比
爆仓数据
清算热力图
订单簿（L2）
Hyperliquid 仓位
主动买卖量
CVD
资金流入流出
现货
市场数据
订单簿
主动买卖量
CVD
资金流入流出
期权
最大痛点
期权相关数据
交易所持仓历史
交易所成交量历史
链上数据
交易所资产透明度
交易所余额
链上转账
大额转账
代币解锁
ETF 数据
比特币 ETF
以太坊 ETF
灰度基金
Solana ETF
XRP ETF
指标
RSI
MA
EMA
BOLL
MACD
ATR
TD Sequential
Coinbase 溢价
AHR999
普尔倍数
Pi 循环顶部指标
彩虹图
恐惧与贪婪指数
稳定币市值
RHODL
NUPL
山寨币季节指数
比特币市值占比
合约与现货成交量比值
其他数据
财经日历
经济数据
财经事件
央行动态
新闻
快讯
账户
账户等级查询
典型使用场景
此 SKILL 适用于以下应用：

根据问题自动匹配对应 API
将自然语言转换为数据查询
构建市场监控面板
生成量化分析逻辑
整合多种数据来源进行分析
构建具备市场理解能力的 AI 助手
1. 衍生品市场分析
可结合：

持仓量
资金费率
多空比
爆仓数据
清算热力图
用途：

判断市场拥挤程度
分析杠杆风险
观察爆仓密集区域
2. 现货资金流分析
可结合：

主动买卖量
订单簿
CVD
价格走势
用途：

判断现货是否主导行情
分析买卖压力
观察流动性变化
3. ETF 资金监控
可结合：

ETF 列表
净资产历史
资金流历史
溢价 / 折价历史
资产管理规模
用途：

跟踪机构资金流向
观察 ETF 情绪
构建 ETF 监控面板
4. 链上与宏观分析
可结合：

交易所储备 / 资产透明度
大额转账
稳定币市值
恐惧与贪婪指数
比特币市值占比
用途：

判断市场周期
分析流动性变化
观察链上资金活动
5. 指标综合判断
可结合：

AHR999
普尔倍数
NUPL
RHODL
彩虹图
山寨币季节指数
用途：

判断市场估值区间
分析长期趋势
识别周期位置
示例问题
你可以向 Agent 提出以下问题：

「分析 BTC 当前的爆仓压力」
「比较 ETH 的资金费率与持仓量变化」
「ETF 资金流是否正在影响市场？」
「当前 BTC 的资金费率、未平仓量和爆仓数据是否同时出现背离？」
「结合资金费率、CVD 和订单流，当前 BTC 市场是被主动买盘还是卖盘主导？」
「如何构建一个 BTC 市场监控面板？」
「哪些 CoinGlass 指标适合判断山寨币市场是否过热？」
「最近 24 小时的爆仓分布是否集中在某个价格区间？是否存在清算密集区？」
「应该组合哪些接口来分析短线市场结构？」
适用对象

企业和机构用户
AI 产品开发者
量化研究员
交易员
数据分析师
加密市场研究团队
Agent 应用开发者
内部工具建设团队
下一步
接入完成后，你可以进一步：

结合 MCP 构建完整数据流程
搭建内部分析工具
开发市场监控系统
打造专属 AI 研究助手
构建可复用的市场分析工作流
