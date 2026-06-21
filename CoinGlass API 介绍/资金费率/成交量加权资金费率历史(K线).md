成交量加权资金费率历史(K线)

> ## Documentation Index
> Fetch the complete documentation index at: https://docs.coinglass.com/llms.txt
> Use this file to discover all available pages before exploring further.

# 成交量加权资金费率历史(K线)

该接口提供按成交量加权的合约币种资金费率 K 线数据，包含开盘价、最高价、最低价和收盘价（OHLC）。

***该接口以下API等级可用：*** [API 等级](https://www.coinglass.com/zh/pricing)：

| API 等级 | 爱好版    | 创业版      | 标准版 | 专业版 | 企业版 |
| :----- | :----- | :------- | :-- | :-- | :-- |
| 可用性    | ✅      | ✅        | ✅   | ✅   | ✅   |
| 颗粒度    | `>=4h` | ​`>=30m` | 无限制 | 无限制 | 无限制 |

### 响应数据

```json
{
  "code": "0",
  "msg": "success",
  "data": [
    {
      "time": 1658880000000, // 时间戳（毫秒）
      "open": "0.004603",     // 开盘资金费率
      "high": "0.009388",     // 最高资金费率
      "low": "-0.005063",     // 最低资金费率
      "close": "0.009229"     // 收盘资金费率
    },
    {
      "time": 1658966400000, // 时间戳（毫秒）
      "open": "0.009229",     // 开盘资金费率
      "high": "0.01",         // 最高资金费率
      "low": "0.007794",      // 最低资金费率
      "close": "0.01"         // 收盘资金费率
    }
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
    "/api/futures/funding-rate/vol-weight-history": {
      "get": {
        "summary": "Vol Weight OHLC History",
        "description": "This API presents volume-weight data through OHLC (Open, High, Low, Close) candlestick charts.",
        "operationId": "vol-weight-ohlc-history",
        "parameters": [
          {
            "name": "symbol",
            "in": "query",
            "required": true,
            "description": "交易币种（例如：BTC）。可通过 support-coins 接口获取支持的币种列表。",
            "schema": {
              "type": "string",
              "default": "BTC"
            }
          },
          {
            "name": "interval",
            "in": "query",
            "required": true,
            "description": "数据的时间间隔。支持的取值包括：1m、3m、5m、15m、30m、1h、4h、6h、8h、12h、1d、1w。",
            "schema": {
              "type": "string",
              "default": "1d"
            }
          },
          {
            "name": "limit",
            "in": "query",
            "required": false,
            "description": "每次请求返回的数据条数。默认值为 1000，最大值为 1000。",
            "schema": {
              "type": "integer",
              "format": "int32",
              "default": "10"
            }
          },
          {
            "name": "start_time",
            "in": "query",
            "required": false,
            "description": "开始时间戳（毫秒）（例如：1641522717000）。",
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
            "description": "结束时间戳（毫秒）（例如：1641522717000）。",
            "schema": {
              "type": "integer",
              "format": "int64",
              "default": ""
            }
          }
        ],
        "responses": {
          "200": {
            "description": "200",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{\n  \"code\": \"0\",\n  \"msg\": \"success\",\n  \"data\": [\n    {\n      \"time\": 1658880000000, // 时间戳（毫秒）\n      \"open\": \"0.004603\",     // 开盘资金费率\n      \"high\": \"0.009388\",     // 最高资金费率\n      \"low\": \"-0.005063\",     // 最低资金费率\n      \"close\": \"0.009229\"     // 收盘资金费率\n    },\n    {\n      \"time\": 1658966400000, // 时间戳（毫秒）\n      \"open\": \"0.009229\",     // 开盘资金费率\n      \"high\": \"0.01\",         // 最高资金费率\n      \"low\": \"0.007794\",      // 最低资金费率\n      \"close\": \"0.01\"         // 收盘资金费率\n    }\n  ]\n}\n"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {}
                }
              }
            }
          },
          "400": {
            "description": "400",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {}
                }
              }
            }
          }
        },
        "deprecated": false
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