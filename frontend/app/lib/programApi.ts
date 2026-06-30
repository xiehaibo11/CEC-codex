import { apiRequest } from './apiClient'

export interface ProgramExecutionLog {
  id: number
  binding_id: number
  account_id: number
  account_name: string
  program_id: number
  program_name: string
  trigger_type: string
  trigger_symbol: string | null
  signal_pool_id: number | null
  signal_pool_name: string | null
  wallet_address: string | null
  success: boolean
  decision_action: string | null
  decision_symbol: string | null
  decision_size_usd: number | null
  decision_leverage: number | null
  decision_reason: string | null
  error_message: string | null
  execution_time_ms: number | null
  market_context: {
    input_data?: {
      environment?: string
      trigger_symbol?: string
      trigger_type?: string
      signal_pool_id?: number
      signal_pool_name?: string
      available_balance?: number
      total_equity?: number
      margin_usage_percent?: number
      positions?: Record<string, { side: string; size: number; entry_price: number; unrealized_pnl?: number; leverage?: number }>
      positions_count?: number
      open_orders_count?: number
      prices?: Record<string, number>
    }
    data_queries?: Array<{ method: string; args: Record<string, unknown>; result: unknown }>
    execution_logs?: string[]
    prices?: Record<string, number>
    available_balance?: number
  } | null
  params_snapshot: Record<string, unknown> | null
  decision_json: Record<string, unknown> | null
  created_at: string
  exchange?: string
}

export async function getProgramExecutions(params?: {
  account_id?: number
  program_id?: number
  environment?: 'testnet' | 'mainnet'
  limit?: number
  before?: string
  after?: string
  action?: string
  exchange?: string
}): Promise<ProgramExecutionLog[]> {
  const search = new URLSearchParams()
  if (params?.account_id) search.append('account_id', params.account_id.toString())
  if (params?.program_id) search.append('program_id', params.program_id.toString())
  if (params?.environment) search.append('environment', params.environment)
  if (params?.limit) search.append('limit', params.limit.toString())
  if (params?.before) search.append('before', params.before)
  if (params?.after) search.append('after', params.after)
  if (params?.action) search.append('action', params.action)
  if (params?.exchange) search.append('exchange', params.exchange)
  const query = search.toString()
  const response = await apiRequest(`/programs/executions/${query ? `?${query}` : ''}`)
  return response.json()
}

export interface TestRunRequest {
  code: string
  symbol?: string
  period?: string
}

export interface ErrorLocation {
  file: string | null
  line: number | null
  column: number | null
  function: string | null
  code_context: string | null
}

export interface DecisionResult {
  action: string
  symbol: string | null
  size_usd: number | null
  leverage: number | null
  reason: string | null
}

export interface MarketDataSummary {
  symbol: string
  current_price: number | null
  price_change_1h: number | null
  klines_count: number
  indicators_loaded: string[]
}

export interface TestRunResponse {
  success: boolean
  decision: DecisionResult | null
  execution_time_ms: number
  market_data: MarketDataSummary | null
  error_type: string | null
  error_message: string | null
  error_traceback: string | null
  error_location: ErrorLocation | null
  suggestions: string[]
  available_apis: Record<string, unknown> | null
}

export async function testRunProgram(request: TestRunRequest): Promise<TestRunResponse> {
  const response = await apiRequest('/programs/test-run', {
    method: 'POST',
    body: JSON.stringify(request),
  })
  return response.json()
}

export interface PreviewRunResponse {
  success: boolean
  error: string | null
  input_data: {
    trigger_symbol: string
    trigger_type: string
    environment: string
    available_balance: number
    total_equity: number
    used_margin: number
    margin_usage_percent: number
    positions: Record<string, {
      side: string
      size: number
      entry_price: number
      unrealized_pnl: number
    }>
    open_orders_count: number
    recent_trades_count: number
    current_price: number | null
  } | null
  data_queries: Array<{
    method: string
    args: Record<string, unknown>
    result: unknown
  }>
  execution_logs: string[]
  decision: Record<string, unknown> | null
  execution_time_ms: number
}

export async function previewRunBinding(bindingId: number): Promise<PreviewRunResponse> {
  const response = await apiRequest(`/programs/bindings/${bindingId}/preview-run`, {
    method: 'POST',
  })
  return response.json()
}

export interface ProgramDevGuideResponse {
  content: string
}

export async function getProgramDevGuide(lang: string = 'en'): Promise<ProgramDevGuideResponse> {
  const response = await apiRequest(`/programs/dev-guide?lang=${lang}`)
  return response.json()
}
