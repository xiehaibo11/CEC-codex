持仓历史(K线)

> ## Documentation Index
> Fetch the complete documentation index at: https://docs.coinglass.com/llms.txt
> Use this file to discover all available pages before exploring further.

# 持仓历史(K线)

该接口提供合约交易对的持仓量（Open Interest）K线数据，包含开盘价、最高价、最低价和收盘价（OHLC）。

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
      "time": 2644845344000, // 时间戳（毫秒）
      "open": "2644845344",   // 开盘持仓量
      "high": "2692643311",   // 最高持仓量
      "low": "2576975597",    // 最低持仓量
      "close": "2608846475"   // 收盘持仓量
    },
    {
      "time": 2608846475000, // 时间戳（毫秒）
      "open": "2608846475",  // 开盘持仓量
      "high": "2620807645",  // 最高持仓量
      "low": "2327236202",   // 最低持仓量
      "close": "2340177420"  // 收盘持仓量
    },
    ....
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
    "/api/futures/open-interest/history": {
      "get": {
        "summary": "OHLC History",
        "description": "This API presents open interest data through OHLC (Open, High, Low, Close) candlestick charts.",
        "operationId": "oi-ohlc-histroy",
        "parameters": [
          {
            "name": "exchange",
            "in": "query",
            "required": true,
            "description": "交易所名称（例如：Binance、OKX）。支持的交易所可通过 support-exchange-pair 接口获取。",
            "schema": {
              "type": "string",
              "default": "Binance"
            }
          },
          {
            "name": "symbol",
            "in": "query",
            "required": true,
            "description": "交易对（例如：BTCUSDT）。支持的交易对可通过 support-exchange-pair 接口获取。",
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
            "description": "起始时间戳（毫秒）（例如：1641522717000）。",
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
          },
          {
            "name": "unit",
            "in": "query",
            "required": false,
            "description": "返回数据的单位，可选值为 'usd' 或 'coin'。",
            "schema": {
              "type": "string",
              "default": "usd"
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
                    "value": "{\n  \"code\": \"0\",\n  \"msg\": \"success\",\n  \"data\": [\n    {\n      \"time\": 2644845344000, // 时间戳（毫秒）\n      \"open\": \"2644845344\",   // 开盘持仓量\n      \"high\": \"2692643311\",   // 最高持仓量\n      \"low\": \"2576975597\",    // 最低持仓量\n      \"close\": \"2608846475\"   // 收盘持仓量\n    },\n    {\n      \"time\": 2608846475000, // 时间戳（毫秒）\n      \"open\": \"2608846475\",  // 开盘持仓量\n      \"high\": \"2620807645\",  // 最高持仓量\n      \"low\": \"2327236202\",   // 最低持仓量\n      \"close\": \"2340177420\"  // 收盘持仓量\n    },\n    ....\n  ]\n}"
                  }
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