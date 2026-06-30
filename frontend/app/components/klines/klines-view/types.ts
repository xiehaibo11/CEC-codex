export type ChartType = 'candlestick' | 'line' | 'area'

export interface MarketData {
  symbol: string
  price: number
  oracle_price: number
  change24h: number
  volume24h: number
  percentage24h: number
  open_interest: number
  funding_rate: number
}

export type FlowIndicatorKey =
  | 'cvd'
  | 'taker_volume'
  | 'oi'
  | 'oi_delta'
  | 'funding'
  | 'depth_ratio'
  | 'order_imbalance'

export type FlowAvailability = Record<FlowIndicatorKey, boolean>
