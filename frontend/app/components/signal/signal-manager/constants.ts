export const WALLET_EVENT_TYPES = [
  'position_change',
  'equity_change',
  'fill',
  'funding',
  'transfer',
  'liquidation',
]

export const FACTOR_CATEGORY_LABELS: Record<string, string> = {
  trend: 'Trend',
  momentum: 'Momentum',
  volatility: 'Volatility',
  volume: 'Volume',
  statistical: 'Statistical',
  composite: 'Composite',
  custom: 'Custom',
}

export const METRICS = [
  { value: 'oi_delta', label: 'OI Delta', desc: 'Open Interest change %. Positive=inflow, Negative=outflow' },
  { value: 'cvd', label: 'CVD', desc: 'Cumulative Volume Delta. Positive=buyers dominate, Negative=sellers dominate' },
  { value: 'funding', label: 'Funding Rate Change', desc: 'Funding rate change (aligned with K-line chart). Positive=rate increasing, Negative=rate decreasing' },
  { value: 'depth_ratio', label: 'Depth Ratio', desc: 'Bid/Ask depth ratio. >1=more bids, <1=more asks' },
  { value: 'taker_ratio', label: 'Taker Ratio', desc: 'Log taker ratio ln(buy/sell). >0=buyers, <0=sellers. Symmetric around 0' },
  { value: 'order_imbalance', label: 'Order Imbalance', desc: 'Order book imbalance (-1 to 1). Positive=buy pressure' },
  { value: 'oi', label: 'OI (Absolute)', desc: 'Absolute Open Interest value in USD' },
  { value: 'taker_volume', label: 'Taker Volume', desc: 'Composite signal: direction + ratio + volume threshold', isComposite: true },
  { value: 'macd', label: 'MACD', desc: 'MACD technical indicator events: golden cross, death cross, etc.', isEvent: true },
  { value: 'price_change', label: 'Price Change', desc: 'Price change % over time window. Formula: (current-prev)/prev*100. Positive=up, Negative=down' },
  { value: 'volatility', label: 'Volatility', desc: 'Price volatility % over time window. Formula: (high-low)/low*100. Always positive, detects swings' },
]

export const TAKER_DIRECTIONS = [
  { value: 'any', label: 'Any Direction', desc: 'Trigger on either buy or sell dominance' },
  { value: 'buy', label: 'Buy Dominant', desc: 'Only trigger when buyers dominate' },
  { value: 'sell', label: 'Sell Dominant', desc: 'Only trigger when sellers dominate' },
]

export const MACD_EVENT_TYPES = [
  { value: 'golden_cross', label: 'Golden Cross', desc: 'MACD crosses above Signal line (bullish)' },
  { value: 'death_cross', label: 'Death Cross', desc: 'MACD crosses below Signal line (bearish)' },
  { value: 'histogram_positive', label: 'Histogram Positive', desc: 'Histogram turns positive (same as golden cross)' },
  { value: 'histogram_negative', label: 'Histogram Negative', desc: 'Histogram turns negative (same as death cross)' },
  { value: 'macd_above_zero', label: 'MACD Above Zero', desc: 'MACD line crosses above zero (bullish confirmation)' },
  { value: 'macd_below_zero', label: 'MACD Below Zero', desc: 'MACD line crosses below zero (bearish confirmation)' },
]

export const OPERATORS = [
  { value: 'abs_greater_than', label: '|x| > (Absolute)', desc: 'Triggers when absolute value exceeds threshold (ignores direction)' },
  { value: 'greater_than', label: '> (Greater)', desc: 'Triggers when value is greater than threshold' },
  { value: 'less_than', label: '< (Less)', desc: 'Triggers when value is less than threshold' },
  { value: 'equals', label: '= (Equals)', desc: 'Triggers when value equals threshold' },
]

export const TIME_WINDOWS = [
  { value: '1m', label: '1 min', desc: 'Very short-term, high noise' },
  { value: '3m', label: '3 min', desc: 'Short-term signals' },
  { value: '5m', label: '5 min', desc: 'Recommended for most signals' },
  { value: '15m', label: '15 min', desc: 'Medium-term, more reliable' },
  { value: '30m', label: '30 min', desc: 'Longer-term trends' },
  { value: '1h', label: '1 hour', desc: 'Major trend changes only' },
  { value: '2h', label: '2 hours', desc: 'Long-term trend confirmation' },
  { value: '4h', label: '4 hours', desc: 'Very long-term, major moves only' },
]
