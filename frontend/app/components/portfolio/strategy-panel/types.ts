export interface StrategyConfig {
  price_threshold: number
  interval_seconds: number
  enabled: boolean
  scheduled_trigger_enabled: boolean
  last_trigger_at?: string | null
  signal_pool_id?: number | null
  signal_pool_ids?: number[] | null
  signal_pool_name?: string | null
  signal_pool_names?: string[] | null
  exchange?: string
}

export interface SignalPool {
  id: number
  pool_name: string
  signal_ids: number[]
  symbols: string[]
  enabled: boolean
  logic?: string
  exchange?: string
  source_type?: string | null
}

export interface GlobalSamplingConfig {
  sampling_interval: number
}

export interface StrategyPanelProps {
  accountId: number
  accountName: string
  refreshKey?: number
  accounts?: Array<{ id: number; name: string; model?: string | null }>
  onAccountChange?: (accountId: number) => void
  accountsLoading?: boolean
}

export interface AccountOption {
  value: string
  label: string
}
