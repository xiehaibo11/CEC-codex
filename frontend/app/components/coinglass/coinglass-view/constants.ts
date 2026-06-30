import type { PlanName } from './types'

export const PLAN_ORDER: PlanName[] = ['Hobbyist', 'Startup', 'Standard', 'Professional', 'Enterprise']

export const INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '6h', '8h', '12h', '1d', '1w']

export const EXCHANGES = ['Binance', 'OKX', 'Bybit', 'Bitget', 'Gate']

export const PLAN_LABELS: Record<string, string> = {
  Hobbyist: '爱好者版',
  Startup: '创业版',
  Standard: '标准版',
  Professional: '专业版',
  Enterprise: '企业版',
}

export const DATASET_LABELS: Record<string, string> = {
  pairs_markets: '交易对市场行情',
  price_history: '价格历史 K 线',
  aggregated_cvd: '聚合 CVD',
  pair_taker_volume: '交易对主动买卖量',
  coin_taker_volume: '币种主动买卖量',
  coin_netflow: '币种净流入',
  open_interest: '聚合持仓量',
  global_long_short: '全局账户多空比',
  funding_rate: '资金费率历史 K 线',
  pair_liquidation: '交易对爆仓历史',
  coin_liquidation: '币种爆仓历史',
  liquidation_orders: '爆仓订单',
  orderbook_depth: '订单簿买卖盘历史',
  fear_greed: '恐惧贪婪指数',
}

export const CATEGORY_LABELS: Record<string, string> = {
  WebSocket: '实时订阅',
  '订单薄(L2)': '订单簿(L2)',
}

export const CHART_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
]

export const minutesByInterval: Record<string, number> = {
  '1m': 1,
  '3m': 3,
  '5m': 5,
  '15m': 15,
  '30m': 30,
  '1h': 60,
  '4h': 240,
  '6h': 360,
  '8h': 480,
  '12h': 720,
  '1d': 1440,
  '1w': 10080,
}
