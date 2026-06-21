# CoinGlass API v4 文档（完整离线版）

> 全部 171 个接口页面，逐字抓取自 https://docs.coinglass.com （含每页的请求参数、响应示例、OpenAPI 定义、套餐可用性）。
> 抓取日期：2026-06-19 ｜ Base URL：`https://open-api-v4.coinglass.com` ｜ 认证 Header：`CG-API-KEY`
> 对接速查见仓库根目录 `coinglass.md`。

## 目录结构（按官方侧边栏分类）

| 分类 | 文件数 | 说明 |
|---|---|---|
| 价格与市场 | 8 | K线、涨跌幅、支持的币种/交易所/交易对、排名、下架 |
| 资金费率 | 9 | 资金费率历史/套利/加权 |
| 持仓量 | 6 | OI 历史K线、聚合、币本位/U本位 |
| 爆仓与清算 | 9 | 爆仓历史、热力图、地图、最大痛点、订单 |
| 多空比 | 5 | 全局/大户账户比、持仓比、净持仓 |
| 订单薄(L2) | 5 | 订单簿历史、大额挂单、热力图 |
| Hyperliquid 仓位 | 9 | 钱包/巨鲸仓位、盈亏分布、多空比 |
| 主动买卖 | 9 | **CVD / 聚合CVD / taker 买卖量**、净流入、足迹图 ← 本项目核心 |
| 现货 | 18 | 现货版 CVD/taker/订单簿/K线/行情 |
| 期权 | 5 | 期权信息、最大痛点、OI/成交量 |
| 链上 | 12 | 交易所资产/余额/透明度、溢价、转账、解锁 |
| ETF | 17 | BTC/ETH/其他 ETF 资金流、净资产、灰度 |
| 指标 | 16 | RSI/MACD/MA/EMA/ATR/TD/布林/基差/CGDI/CDRI |
| 其他 | 32 | 宏观链上指标（AHR999、恐惧贪婪、NUPL、M2 等）、新闻、经济数据 |
| 账号 | 1 | 账户等级/额度查询 |
| 文档与支持 | 8 | 快速开始、认证、错误码与限流、端点总览、更新日志、MCP、Agent技能、企业定制 |
| WebSocket | 5 | 基础介绍、爆仓/现货成交/合约成交/合约Ticker 实时流 |

## 与本项目（event-contract）最相关

- `主动买卖/聚合CVD.md` → `GET /api/futures/aggregated-cvd/history`（多交易所聚合 CVD + taker 买卖量）
- `主动买卖/CVD.md` → `GET /api/futures/cvd/history`（单交易所）
- `主动买卖/币种主动买卖量历史.md`、`交易对主动买卖量历史.md`
- `价格与市场/价格历史K线.md` → `GET /api/futures/price/history`（结算锚点 open）
- `爆仓与清算/*`、`多空比/*` → 可喂给 `regime.py` 做状态门控

## 备注

- 每个 `.md` 文件含官方的 **Response Data 示例**与 **OpenAPI definition**（含完整参数 schema），可直接据此写客户端。
- `_旧版本(可删)/` 是之前一次半成品抓取的残留（命名不统一），内容已被本套完整文档覆盖，确认无误后可整个删除。
