连接 CoinGlass MCP ，您的 AI 模型或 Agent 可以直接查询 CoinGlass 数据并生成分析结果。

使用 CoinGlass MCP，AI 可以做什么？
借助 CoinGlass MCP，AI Agent 可以：

分析衍生品市场

查询资金费率趋势
监控未平仓量变化
分析爆仓分布
识别市场情绪

追踪多空持仓变化
检测市场过热或恐慌
跟踪资金流向

查看 ETF 资金流入流出
监控交易所持仓变化
生成市场报告

自动总结市场趋势
生成每日市场分析
构建自动化 Agent

构建市场监控机器人
构建交易信号系统
通过 MCP，AI 可以直接理解 CoinGlass API，而无需开发者手动阅读复杂的 API 文档。

快速开始（新手教程）
CoinGlass MCP Server 地址


https://api-mcp.coinglass.com/mcp
如果需要执行 API 请求，需要在 MCP 配置中提供你的 CoinGlass API Key。

MCP 配置
CursorWindsurfClaude Desktop
步骤 1：安装并打开 Cursor

如果尚未安装 Cursor，请访问：


https://cursor.sh
下载并安装 Cursor，然后启动应用。

步骤 2：创建 MCP 配置文件

Cursor 会自动读取名为 mcp.json 的配置文件。

推荐在你的项目目录中创建以下文件：


.cursor/mcp.json
示例目录结构：


your-project
├── .cursor
│   └── mcp.json
├── src
└── README.md
你也可以使用全局配置（适用于所有 Cursor 项目）：


~/.cursor/mcp.json
步骤 3：添加 CoinGlass MCP 配置

在 mcp.json 文件中添加以下内容：

JSON

{
  "mcpServers": {
    "coinglass-api": {
      "url": "https://api-mcp.coinglass.com/mcp",
      "headers": {
        "CG-API-KEY": "YOUR_API_KEY"
      }
    }
  }
}
请将 YOUR_API_KEY 替换为你的 CoinGlass API Key。

步骤 4：重新启动 Cursor

保存文件后，关闭并重新打开 Cursor。
Cursor 会自动加载 MCP 配置。

支持的 MCP 客户端
CoinGlass MCP 可以与多种 AI 工具一起使用，包括：

Claude Desktop
Cursor
Windsurf
VSCode
Claude Code CLI
Open Code CLI
Google Gemini CLI
MCP Inspector
Cline
OpenClaw（通过 MCPorter）
推荐使用 Cursor 或 Claude Desktop 进行快速体验。

测试 MCP 连接
完成配置后：

打开你的 AI 客户端（Cursor、Claude、Windsurf）
创建一个新的 AI 对话
输入 CoinGlass 查询
示例查询（Prompt Examples）
你可以直接在 AI 客户端中输入自然语言查询。

清算分析


获取 BTC 最近 7 天清算热力图，并分析可能的强平区间。
资金费率趋势


查询过去 7 天 BTC 的资金费率趋势，现在市场偏多还是偏空？
交易所对比


对比 Binance 和 OKX 当前 ETH 的持仓量差异。
订单薄


查看当前 BTC 的订单薄深度分布，分析主要买卖盘集中在哪些价格区间？是否存在明显的支撑位和阻力位？
ETF 资金流


今天 BTC ETF 的资金是流入还是流出？
爆仓统计


过去 24 小时全网爆仓最多的币种是什么？
市场总结


根据当前持仓量、资金费率和恐慌指数生成市场摘要。


可用 MCP 工具
CoinGlass MCP Server 当前提供30多个工具，例如：

get_futures_liquidation_exchange_list
列出交易所合约爆仓列表。

get_bitcoin_etf_flow_history
获取Bitcoin ETF 流入流出历史。

get_futures_aggregated_open_interest_history
获取币种的聚合持仓历史。

get_futures_funding_rate_history
获取合约资金费率历史。

MCP 与 REST API 的区别
使用 MCP 的场景：

Agent 自动化：构建能够根据市场数据触发预警或执行策略的智能体。
交易监控：实时获取全网爆仓分布，识别市场极端情绪。
自然语言查数据：告别复杂的 API 调试，直接用口语询问数据。
市场快报：让 AI 自动汇总今日市场热点与资金流向。
深度研究：分析特定币种的历史持仓与价格背离。
使用 REST API 的场景：

后端服务
自动化脚本
高性能数据请求
生产环境系统
限制与已知问题
Beta 状态

CoinGlass MCP Server 当前处于 Beta 阶段，部分 Tool schema 可能随 API 更新发生变化。

速率限制

MCP 请求受 CoinGlass API Key 的配额限制。

建议使用较高配额的 API Key 以获得最佳体验。

安全提示
切勿在公开代码仓库中暴露你的 API Key。

请始终安全地存储 API 密钥，并避免提交包含敏感信息的配置文件。