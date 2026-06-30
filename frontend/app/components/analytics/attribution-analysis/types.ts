export interface SummaryMetrics {
  total_pnl: number
  total_fee: number
  net_pnl: number
  trade_count: number
  win_count: number
  loss_count: number
  win_rate: number
  avg_win: number | null
  avg_loss: number | null
  profit_factor: number | null
}

export interface DataCompleteness {
  total_decisions: number
  with_strategy: number
  with_signal: number
  with_pnl: number
}

export interface TriggerBreakdown {
  count: number
  net_pnl: number
}

export interface SummaryResponse {
  period: { start: string | null; end: string | null }
  overview: SummaryMetrics
  data_completeness: DataCompleteness
  by_trigger_type: Record<string, TriggerBreakdown>
}

export interface DimensionItem {
  metrics: SummaryMetrics
  by_trigger_type?: Record<string, TriggerBreakdown>
  [key: string]: unknown
}

export interface DimensionResponse {
  items: DimensionItem[]
  unattributed?: { count: number; metrics: SummaryMetrics | null }
}

export interface Account {
  id: number
  name: string
  account_type: string
  model?: string
}

export interface TradeDetail {
  id: number
  source?: 'ai' | 'program'
  symbol: string
  decision_time: string | null
  entry_time: string | null
  exit_time: string | null
  entry_type: string
  exit_type: string
  gross_pnl: number
  fees: number
  net_pnl: number
  tags: string[]
  hyperliquid_order_id: string | null
  tp_order_id: string | null
  sl_order_id: string | null
}

export interface TradesResponse {
  trades: TradeDetail[]
  total: number
  limit: number
  offset: number
  account_equity: number
  loss_threshold: number
}
