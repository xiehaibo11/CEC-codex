交易对K线历史

> ## Documentation Index
> Fetch the complete documentation index at: https://docs.coinglass.com/llms.txt
> Use this file to discover all available pages before exploring further.

# 交易对K线历史

该接口提供加密货币在指定时间周期内的历史开盘价、最高价、最低价和收盘价（OHLC）数据。

***缓存 / 更新频率:*** 实时更新.

***该接口以下API等级可用：*** [API 等级](https://www.coinglass.com/zh/pricing)：

| API 等级 | 爱好版    | 创业版      | 标准版 | 专业版 | 企业版 |
| :----- | :----- | :------- | :-- | :-- | :-- |
| 可用性    | ✅      | ✅        | ✅   | ✅   | ✅   |
| 颗粒度    | `>=4h` | ​`>=30m` | 无限制 | 无限制 | 无限制 |

### 响应数据

```json
{
  "code": "0",
  "data": [
    {
      "time": 1745366400000,
      "open": "93404.9",
      "high": "93864.9",
      "low": "92730",
      "close": "92858.2",
      "volume_usd": "1166471854.3026"
    },
    {
      "time": 1745370000000,
      "open": "92858.2",
      "high": "93464.8",
      "low": "92552",
      "close": "92603.8",
      "volume_usd": "871812560.3437"
    },
    ...
 ]
}    
```

# OpenAPI definition

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "coinglass",
    "version": "3.0"
  },
  "servers": [
    {
      "url": "https://open-api-v4.coinglass.com"
    }
  ],
  "components": {
    "securitySchemes": {
      "sec0": {
        "type": "apiKey",
        "in": "header",
        "name": "CG-API-KEY"
      }
    }
  },
  "security": [
    {
      "sec0": []
    }
  ],
  "paths": {
    "/api/futures/price/history": {
      "get": {
        "summary": "Price OHLC History",
        "description": "The API retrieves historical data of the open, high, low, and close (OHLC) prices for cryptocurrencies.",
        "operationId": "price-ohlc-history",
        "parameters": [
          {
            "name": "exchange",
            "in": "query",
            "required": true,
            "description": "合约交易所名称（例如：Binance、OKX）。可通过 support-exchange-pair 接口获取支持的交易所。",
            "schema": {
              "type": "string",
              "default": "Binance"
            }
          },
          {
            "name": "symbol",
            "in": "query",
            "required": true,
            "description": "交易对（例如：BTCUSDT）。可通过 support-exchange-pair 接口查询支持的交易对。",
            "schema": {
              "type": "string",
              "default": "BTCUSDT"
            }
          },
          {
            "name": "interval",
            "in": "query",
            "required": true,
            "description": "数据时间间隔。支持的取值包括：1m、3m、5m、15m、30m、1h、4h、6h、8h、12h、1d、1w。",
            "schema": {
              "type": "string",
              "default": "1h"
            }
          },
          {
            "name": "limit",
            "in": "query",
            "required": true,
            "description": "每次请求返回的数据条数。默认值：1000，最大值：1000。",
            "schema": {
              "type": "integer",
              "format": "int32",
              "default": 10
            }
          },
          {
            "name": "start_time",
            "in": "query",
            "required": false,
            "description": "起始时间戳，单位为毫秒（例如：1641522717000）。",
            "schema": {
              "type": "integer",
              "format": "int64",
              "default": ""
            }
          },
          {
            "name": "end_time",
            "in": "query",
            "required": false,
            "description": "结束时间戳，单位为毫秒（例如：1641522717000）。",
            "schema": {
              "type": "integer",
              "format": "int64",
              "default": ""
            }
          }
        ],
        "deprecated": false,
        "responses": {
          "200": {
            "description": "OK",
            "content": {
              "application/json": {
                "examples": {
                  "New Example": {
                    "summary": "New Example",
                    "value": "{\n  \"code\": \"0\",\n  \"data\": [\n    {\n      \"time\": 1745366400000,\n      \"open\": \"93404.9\",\n      \"high\": \"93864.9\",\n      \"low\": \"92730\",\n      \"close\": \"92858.2\",\n      \"volume_usd\": \"1166471854.3026\"\n    },\n    {\n      \"time\": 1745370000000,\n      \"open\": \"92858.2\",\n      \"high\": \"93464.8\",\n      \"low\": \"92552\",\n      \"close\": \"92603.8\",\n      \"volume_usd\": \"871812560.3437\"\n    },\n    ...\n ]\n}    "
                  }
                }
              }
            }
          }
        }
      }
    }
  },
  "x-readme": {
    "headers": [],
    "explorer-enabled": true,
    "proxy-enabled": true
  },
  "x-readme-fauxas": true
}
```