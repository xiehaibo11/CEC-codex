import { apiRequest } from './apiClient'

export interface MarketFlowSummaryItem {
  symbol: string
  exchange: string
  window: string
  start_time: number
  end_time: number
  latest_trade_timestamp?: number | null
  total_buy_notional: number
  total_sell_notional: number
  net_inflow: number
  buy_ratio: number
  total_large_buy_notional: number
  total_large_sell_notional: number
  large_order_net: number
  retail_net: number
  large_buy_count: number
  large_sell_count: number
  open_interest_change_pct?: number | null
  funding_rate_pct?: number | null
}

export interface MarketFlowSummaryResponse {
  exchange: string
  window: string
  items: MarketFlowSummaryItem[]
}

export interface NewsArticle {
  id: number
  source_domain: string
  source_url: string
  title: string
  summary?: string | null
  published_at?: string | null
  symbols: string[]
  sentiment?: string | null
  ai_summary?: string | null
  relevance_score?: number | null
  image_url?: string | null
}

export interface HyperAiInsightRequest {
  context: Record<string, unknown>
  selected_event?: Record<string, unknown> | null
  lang?: string
}

export async function startHyperAiInsightAnalysis(payload: HyperAiInsightRequest) {
  const response = await apiRequest('/hyper-ai/insight', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return response.json() as Promise<{ task_id: string }>
}

export interface NewsArticleListResponse {
  items: NewsArticle[]
  total: number
}

export interface LargeOrderZoneItem {
  time: number
  large_buy_notional: number
  large_sell_notional: number
  large_order_net: number
  large_buy_count: number
  large_sell_count: number
}

export interface LargeOrderZoneResponse {
  symbol: string
  exchange: string
  timeframe: string
  items: LargeOrderZoneItem[]
}

export async function getMarketFlowSummary(params: {
  symbols: string[]
  exchange: 'hyperliquid' | 'binance'
  window?: string
}) {
  const searchParams = new URLSearchParams()
  searchParams.set('symbols', params.symbols.join(','))
  searchParams.set('exchange', params.exchange)
  searchParams.set('window', params.window || '1h')
  const response = await apiRequest(`/market-flow/summary?${searchParams.toString()}`)
  return response.json() as Promise<MarketFlowSummaryResponse>
}

export async function getNewsArticles(params: {
  symbols?: string[]
  hours?: number
  limit?: number
}) {
  const searchParams = new URLSearchParams()
  if (params.symbols?.length) {
    searchParams.set('symbols', params.symbols.join(','))
  }
  if (params.hours) {
    searchParams.set('hours', String(params.hours))
  }
  if (params.limit) {
    searchParams.set('limit', String(params.limit))
  }
  const response = await apiRequest(`/news/articles?${searchParams.toString()}`)
  return response.json() as Promise<NewsArticleListResponse>
}

export async function getLargeOrderZones(params: {
  symbol: string
  exchange: 'hyperliquid' | 'binance'
  timeframe: string
  startTime?: number
  endTime?: number
}) {
  const searchParams = new URLSearchParams()
  searchParams.set('symbol', params.symbol)
  searchParams.set('exchange', params.exchange)
  searchParams.set('timeframe', params.timeframe)
  if (params.startTime) searchParams.set('start_time', String(params.startTime))
  if (params.endTime) searchParams.set('end_time', String(params.endTime))
  const response = await apiRequest(`/market-flow/large-order-zones?${searchParams.toString()}`)
  return response.json() as Promise<LargeOrderZoneResponse>
}
