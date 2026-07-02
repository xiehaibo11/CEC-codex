
## MarketData Object (passed to should_trade as 'data')

### Properties (Direct Access)
- data.available_balance: float - Available balance in USD (e.g., 10000.0)
- data.total_equity: float - Total account equity including unrealized PnL (e.g., 10250.5)
- data.used_margin: float - Currently used margin (e.g., 1500.0)
- data.margin_usage_percent: float - Margin usage percentage 0-100 (e.g., 15.0 means 15%)
- data.maintenance_margin: float - Maintenance margin requirement (e.g., 750.0)
- data.trigger_symbol: str - Symbol that triggered this evaluation (empty string "" for scheduled triggers)
- data.trigger_type: str - "signal" or "scheduled"
- data.positions: Dict[str, Position] - Current open positions (keyed by symbol)
- data.recent_trades: List[Trade] - Recent closed trades history (most recent first)
- data.open_orders: List[Order] - Current open orders (TP/SL, limit orders)

### Position Object (from data.positions)
- pos.symbol: str - Trading symbol
- pos.side: str - "long" or "short"
- pos.size: float - Position size
- pos.entry_price: float - Entry price
- pos.unrealized_pnl: float - Unrealized PnL
- pos.leverage: int - Leverage used
- pos.liquidation_price: float - Liquidation price
- pos.opened_at: int or None - Timestamp in milliseconds when position was opened
- pos.opened_at_str: str or None - Human-readable opened time (e.g., "2026-01-15 10:30:00 UTC")
- pos.holding_duration_seconds: float or None - How long position has been held in seconds
- pos.holding_duration_str: str or None - Human-readable duration (e.g., "2h 30m")

### Trade Object (from data.recent_trades)
- trade.symbol: str - Trading symbol (e.g., "BTC")
- trade.side: str - "Long" or "Short"
- trade.size: float - Trade size (e.g., 0.5)
- trade.price: float - Close price (e.g., 95000.0)
- trade.timestamp: int - Close timestamp in milliseconds (e.g., 1736690000000)
- trade.pnl: float - Realized profit/loss in USD (e.g., 125.50)
- trade.close_time: str - Close time in UTC string format (e.g., "2026-01-12 15:30:00 UTC")

### Order Object (from data.open_orders)
- order.order_id: int - Unique order ID (e.g., 12345678)
- order.symbol: str - Trading symbol (e.g., "BTC")
- order.side: str - "Buy" or "Sell"
- order.direction: str - "Open Long", "Open Short", "Close Long", "Close Short"
- order.order_type: str - "Limit", "Stop Limit", "Take Profit Limit"
- order.size: float - Order size (e.g., 0.1)
- order.price: float - Limit price (e.g., 95000.0)
- order.trigger_price: float - Trigger price for stop/TP orders (e.g., 94500.0)
- order.reduce_only: bool - Whether this is a reduce-only order
- order.timestamp: int - Order placement timestamp in milliseconds (e.g., 1736697952000)

### Methods

#### data.get_indicator(symbol: str, indicator: str, period: str) -> dict
Get technical indicator values.
- symbol: "BTC", "ETH", etc.
- indicator: "RSI14", "RSI7", "MA5", "MA10", "MA20", "EMA20", "EMA50", "EMA100", "MACD", "BOLL", "ATR14", "VWAP", "STOCH", "OBV"
- period: "1m", "5m", "15m", "1h", "4h", "1d"
- Returns:
  - RSI/MA/EMA/ATR/VWAP/OBV: {"value": 45.2} (float)
  - MACD: {"macd": 123.5, "signal": 98.2, "histogram": 25.3}
  - BOLL: {"upper": 96500.0, "middle": 95000.0, "lower": 93500.0}
  - STOCH: {"k": 65.3, "d": 58.7}

#### data.get_klines(symbol: str, period: str, count: int = 50) -> list
Get K-line (candlestick) data.
- symbol: "BTC", "ETH", etc.
- period: "1m", "5m", "15m", "1h", "4h", "1d"
- count: Number of candles to return (default 50)
- Returns: List of Kline objects with: timestamp (int seconds), open, high, low, close, volume (all float)

#### data.get_market_data(symbol: str) -> dict
Get complete market data (price, volume, open interest, funding rate).
**Reuses AI Trader's data layer** - same source as {BTC_market_data} variable.
- symbol: "BTC", "ETH", "SOL", etc.
- Returns: Dict with fields:
  - "symbol": "BTC"
  - "price": 95220.0 (mark price)
  - "oracle_price": 95172.0
  - "change24h": 159.0 (USD)
  - "percentage24h": 0.167 (%)
  - "volume24h": 1781547.32 (USD)
  - "open_interest": 10872198.65 (USD)
  - "funding_rate": 0.0000125
- Example: btc_data = data.get_market_data("BTC"); funding = btc_data.get("funding_rate", 0)

**IMPORTANT: Price Access**
- To get current price, use data.get_market_data(symbol) and extract the "price" field
- Example: market_data = data.get_market_data("BTC"); price = market_data.get("price", 0)
- This method returns complete market data (price, volume, OI, funding rate) in one API call
- Do NOT use data.prices (removed) - always use get_market_data() instead

#### data.get_flow(symbol: str, metric: str, period: str) -> dict
Get market flow metrics. All metrics include `last_5` for trend analysis.
- symbol: "BTC", "ETH", etc.
- metric: "CVD", "OI", "OI_DELTA", "TAKER", "FUNDING", "DEPTH", "IMBALANCE"
- period: "1m", "5m", "15m", "1h", "4h", "1d"
- Returns (with real data examples):
  - "CVD": {"current": 14877256.20, "last_5": [...], "cumulative": 17906808.24, "period": "1h"}
  - "OI": {"current": 16826201.53, "last_5": [...], "period": "1h"}
  - "OI_DELTA": {"current": 0.595, "last_5": [...], "period": "1h"} (% change)
  - "TAKER": {"buy": 18915411.13, "sell": 4038154.92, "ratio": 4.684, "ratio_last_5": [...], "volume_last_5": [...], "period": "1h"}
  - "FUNDING": {"current": 11.2, "current_pct": 0.00112, "change": 1.55, "change_pct": 0.000155, "last_5": [...], "annualized": 1.2264, "period": "1h"}
  - "DEPTH": {"bid": 28.34, "ask": 0.04, "ratio": 635.07, "ratio_last_5": [...], "spread": 1.0, "period": "1h"}
  - "IMBALANCE": {"current": 0.997, "last_5": [...], "period": "1h"} (-1 to +1)

#### data.get_regime(symbol: str, period: str) -> RegimeInfo
Get market regime classification.
- symbol: "BTC", "ETH", etc.
- period: "1m", "5m", "15m", "1h", "4h", "1d"
- Returns: RegimeInfo object
  - regime.regime: "breakout", "absorption", "stop_hunt", "exhaustion", "trap", "continuation", "noise"
  - regime.conf: 0.85 (confidence 0.0-1.0)
  - regime.direction: "bullish", "bearish", "neutral"
  - regime.reason: "Strong buying pressure with OI expansion"
  - regime.indicators: {"cvd_ratio": 0.997, "oi_delta": 0.595, "taker_ratio": 4.684, "price_atr": 0.5, "rsi": 55.2}

#### data.get_price_change(symbol: str, period: str) -> dict
Get price change over period.
- symbol: "BTC", "ETH", etc.
- period: "1m", "5m", "15m", "1h", "4h", "1d"
- Returns: {"change_percent": 2.5, "change_usd": 2350.0}

#### data.get_factor(symbol: str, factor_name: str, period: str = "5m") -> dict
Get factor value and effectiveness metrics for a specific K-line period.
- symbol: "BTC", "ETH", etc.
- factor_name: "RSI21", "MOM10", "VOL_RATIO", or any custom factor name
- period: "1m", "5m", "15m", "1h", "4h", "1d" (explicit for new code; omitted defaults to 5m for backward compatibility)
- Returns: {"factor_name": "RSI21", "symbol": "BTC", "period": "1h", "id": 5, "expression": "RSI(close, 21)", "description": "...", "category": "momentum", "value": 0.0234, "ic": 0.05, "icir": 1.35, "win_rate": 58.2, "decay_half_life_hours": -1}
- decay_half_life_hours: -1=persistent, positive=half-life hours, None=insufficient data
- Use `query_factors` tool to see all available factor names

#### data.get_factor_ranking(symbol: str, top_n: int = 10) -> list
Get top factors ranked by |ICIR| (most reliable first).
- Returns: [{"factor_name": "SKEW20", "id": 12, "expression": "SKEW(RET(close,1),20)", "description": "...", "ic": -0.08, "icir": -2.1, "win_rate": 62.0, "decay_half_life_hours": -1}, ...]
- Not available in backtest mode

### Available in Sandbox
- time: Pre-injected sandbox object, use `time.time()` directly without importing
- math: Pre-injected sandbox object, use `math.sqrt()` / `math.log()` / `math.exp()` directly without importing
- log(message): Debug output function
