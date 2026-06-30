export interface SignalDefinition {
  id: number
  signal_name: string
  description: string | null
  trigger_condition: TriggerCondition
  enabled: boolean
  exchange: string
  created_at: string
  updated_at: string
}

export interface TriggerCondition {
  metric?: string
  operator?: string
  threshold?: number
  time_window?: string
  logic?: string
  conditions?: TriggerCondition[]
}

export interface SignalPool {
  id: number
  pool_name: string
  signal_ids: number[]
  symbols: string[]
  enabled: boolean
  logic: 'OR' | 'AND'
  exchange: string
  source_type?: PoolSourceType
  source_config?: {
    addresses?: string[]
    event_types?: string[]
    sync_mode?: string
  }
  created_at: string
}

export interface MarketRegimeData {
  regime: string
  direction: string
  confidence: number
  details?: Record<string, unknown>
}

export interface SignalTriggerLog {
  id: number
  signal_id: number | null
  pool_id: number | null
  symbol: string
  trigger_value: Record<string, unknown> | null
  triggered_at: string
  market_regime: MarketRegimeData | null
}

export interface WalletTrackingRuntimeStatus {
  enabled: boolean
  configured?: boolean
  source?: string
  status: string
  tier: string | null
  key_source?: string | null
  key_masked?: string | null
  synced_addresses: string[]
  last_connected_at: string | null
  last_message_at: string | null
  last_event_at: string | null
  last_error: string | null
  active_wallet_pool_count: number
  token_synced_at: string | null
}

export interface FactorItem {
  name: string
  category: string
  description: string
  expression: string
  source: string
}

export interface MarketRegimeResult {
  symbol: string
  regime: string
  direction: string
  confidence: number
  reason: string
}

export interface MetricAnalysis {
  status: string
  symbol: string
  metric: string
  period: string
  sample_count: number
  time_range_hours: number
  warning?: string
  statistics?: {
    mean: number
    std: number
    min: number
    max: number
    abs_percentiles: { p75: number; p90: number; p95: number; p99: number }
  }
  suggestions?: {
    aggressive: { threshold: number; description: string }
    moderate: { threshold: number; description: string; recommended?: boolean }
    conservative: { threshold: number; description: string }
  }
  message?: string
}

export type PoolSourceType = 'market_signals' | 'wallet_tracking'

export type SignalTranslate = (key: string, fallback?: string) => string
