# 架构详细图

本目录基于当前 CEC-codex 仓库生成，2026-07-04 由 Claude 在分支 `refactor/code-split`
上做了深度校验更新（逐一核对 `main.py` 全部 34 处 `include_router`、前端全部 hash
页面、调度任务真实周期、双库读写归属），并新增事件合约纸面交易与滚动验证深度章节。

## 文件

- `CEC-codex-前后端架构详细图.md`：完整 Markdown + Mermaid 架构图（13 章、12 张图）。
- `index.html`：可直接用浏览器打开的 Mermaid 渲染版本；需要能加载 Mermaid CDN。
- `mermaid/*.mmd`：每张图的原始 Mermaid 源码，方便复制到 Mermaid Live Editor 或文档系统。

## 推荐查看方式

1. 在支持 Mermaid 的 Markdown 查看器打开 `CEC-codex-前后端架构详细图.md`。
2. 或双击 `index.html` 查看图形化版本。
3. 如果 HTML 打开后图不渲染，说明当前环境无法加载 CDN；请使用 Markdown 或 `mermaid/*.mmd`。

## 本次深度校验修正的关键事实

- AI Stream（`/api/ai-stream/{task_id}?offset=`）是缓冲长轮询，不是原生 SSE。
- 快照库（`SNAPSHOT_DATABASE_URL`）只有 Hyperliquid 子系统写入（两张表）；
  Binance/HiBT 账户快照都在主库。
- 路由表补齐 5 个此前遗漏的 router：`/api/config`、`/api/sampling`、
  `/api/market-regime`、`/api/trader`、`/api/prompt-backtest`。
- `backend/app_routers.py` 是代码拆分残留，`main.py` 尚未调用它（仍内联注册）。
- 设置页 `BinanceDataSettingsTab` 已删除，Binance/HiBT 共用 `ExchangeDataSettingsTab`；
  `SettingsPage` 现为 Watchlist / Binance-Data / HiBT-Data / News-Sources 四个 Tab。
- `EventPaperTraderCard` 及其子组件已从 `components/portfolio/` 移至 `components/analytics/`。
