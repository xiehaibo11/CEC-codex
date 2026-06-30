import type { ChartType, FlowAvailability, FlowIndicatorKey } from './types'

export const KLINE_PERIODS = [
  '1m',
  '3m',
  '5m',
  '15m',
  '30m',
  '1h',
  '2h',
  '4h',
  '6h',
  '8h',
  '12h',
  '1d',
  '3d',
  '1w',
  '1M',
]

export const CHART_TYPES: Array<{
  value: ChartType
  labelKey: string
  fallback: string
}> = [
  { value: 'candlestick', labelKey: 'kline.candlestick', fallback: 'Candlestick' },
  { value: 'line', labelKey: 'kline.line', fallback: 'Line' },
  { value: 'area', labelKey: 'kline.area', fallback: 'Area' },
]

export const FLOW_INDICATORS: Array<{ key: FlowIndicatorKey; label: string }> = [
  { key: 'cvd', label: 'CVD' },
  { key: 'taker_volume', label: 'Taker Vol' },
  { key: 'oi', label: 'OI' },
  { key: 'oi_delta', label: 'OI Delta' },
  { key: 'funding', label: 'Funding' },
  { key: 'depth_ratio', label: 'Depth(log)' },
  { key: 'order_imbalance', label: 'Imbalance' },
]

export const TECHNICAL_INDICATOR_GROUPS = [
  {
    labelKey: 'kline.trend',
    fallback: 'Trend',
    indicators: ['MA5', 'MA10', 'MA20', 'EMA20', 'EMA50', 'EMA100'],
  },
  {
    labelKey: 'kline.volume',
    fallback: 'Volume',
    indicators: ['VWAP', 'OBV'],
  },
  {
    labelKey: 'kline.momentum',
    fallback: 'Momentum',
    indicators: ['RSI14', 'RSI7', 'STOCH', 'MACD'],
  },
  {
    labelKey: 'kline.volatility',
    fallback: 'Volatility',
    indicators: ['BOLL', 'ATR14'],
  },
]

const PERIOD_MINUTES: Record<string, number> = {
  '1m': 1,
  '3m': 3,
  '5m': 5,
  '15m': 15,
  '30m': 30,
  '1h': 60,
  '2h': 120,
  '4h': 240,
  '6h': 360,
  '8h': 480,
  '12h': 720,
  '1d': 1440,
  '3d': 4320,
  '1w': 10080,
  '1M': 43200,
}

export function getFlowIndicatorAvailability(period: string): FlowAvailability {
  const minutes = PERIOD_MINUTES[period] || 1

  return {
    cvd: true,
    taker_volume: true,
    oi: minutes >= 5,
    oi_delta: minutes >= 5,
    funding: true,
    depth_ratio: true,
    order_imbalance: true,
  }
}

export function formatCompactNumber(value: number) {
  if (!value && value !== 0) return '-'
  const abs = Math.abs(value)
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${(value / 1_000).toFixed(2)}K`
  return value.toLocaleString()
}
