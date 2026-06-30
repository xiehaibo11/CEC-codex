export type PlanName = 'Hobbyist' | 'Startup' | 'Standard' | 'Professional' | 'Enterprise'

export interface CoinGlassParam {
  name: string
  required: boolean
  type: string
  default?: string | number | null
  description?: string
}

export interface CoinGlassEndpoint {
  id: string
  title: string
  category: string
  path: string
  method?: string
  summary: string
  params: CoinGlassParam[]
  required_params: string[]
  min_plan?: PlanName | null
  availability?: Record<string, boolean | null>
  interval_limit?: Record<string, string | null>
  doc_path: string
}

export interface CoinGlassDataset {
  id: string
  label: string
  category: string
  path: string
  focus: string
  default_params: Record<string, string>
  endpoint?: CoinGlassEndpoint
}

export interface CoinGlassCatalog {
  total: number
  categories: Array<{ name: string; count: number; startup_available: number; standard_plus: number }>
  endpoints: CoinGlassEndpoint[]
  datasets: CoinGlassDataset[]
}

export interface CoinGlassSubscription {
  configured: boolean
  user_key_configured?: boolean
  server_key_configured?: boolean
  key_source?: 'user' | 'server' | 'none'
  key_masked?: string | null
  ok?: boolean
  status?: string | null
  reason?: string | null
  level?: string | null
  expired?: boolean | null
  expire_time?: number | null
}

export type ParamOverrides = Partial<Record<
  'symbol' | 'exchange' | 'exchange_list' | 'interval' | 'limit' | 'range' | 'min_liquidation_amount',
  string | number | null | undefined
>>
