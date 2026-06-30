import { apiRequest } from './apiClient'
import type { StrategyTriggerMode } from './accountApi'

export interface ArenaAccountMeta {
  account_id: number
  name: string
  model?: string | null
}

export interface ArenaRelatedOrder {
  type: 'sl' | 'tp'
  price: number
  quantity: number
  notional: number
  commission: number
  trade_time?: string | null
}

export interface ArenaTrade {
  trade_id: number
  order_id?: number | null
  order_no?: string | null
  account_id: number
  account_name: string
  model?: string | null
  side: string
  direction: string
  symbol: string
  market: string
  price: number
  quantity: number
  notional: number
  commission: number
  trade_time?: string | null
  wallet_address?: string | null
  signal_trigger_id?: number | null
  prompt_template_id?: number | null
  prompt_template_name?: string | null
  decision_source_type?: 'prompt_template' | 'program' | null
  related_orders?: ArenaRelatedOrder[]
  exchange?: string
}

export interface ArenaTradesResponse {
  generated_at: string
  accounts: ArenaAccountMeta[]
  trades: ArenaTrade[]
}

export async function getArenaTrades(params?: { limit?: number; account_id?: number; trading_mode?: string; wallet_address?: string, symbol?: string, exchange?: string }): Promise<ArenaTradesResponse> {
  const search = new URLSearchParams()
  if (params?.limit) search.append('limit', params.limit.toString())
  if (params?.account_id) search.append('account_id', params.account_id.toString())
  if (params?.trading_mode) search.append('trading_mode', params.trading_mode)
  if (params?.wallet_address) search.append('wallet_address', params.wallet_address)
  if (params?.symbol) search.append('symbol', params.symbol)
  if (params?.exchange) search.append('exchange', params.exchange)
  const query = search.toString()
  const response = await apiRequest(`/arena/trades${query ? `?${query}` : ''}`)
  return response.json()
}

export interface UpdatePnlEnvironmentResult {
  fills_count: number
  unique_orders: number
  trades_updated: number
  trades_created: number
  decisions_updated: number
  program_logs_updated: number
  skipped: number
  historical_fixed?: number
}

export interface UpdatePnlResponse {
  success: boolean
  message?: string
  hyperliquid: Record<string, UpdatePnlEnvironmentResult>
  binance: Record<string, UpdatePnlEnvironmentResult>
  errors: string[]
}

export async function updateArenaPnl(): Promise<UpdatePnlResponse> {
  const response = await apiRequest('/arena/update-pnl', { method: 'POST' })
  return response.json()
}

export interface PnlSyncStatus {
  needs_sync: boolean
  unsync_count: number
}

export async function checkPnlSyncStatus(tradingMode?: string): Promise<PnlSyncStatus> {
  const params = new URLSearchParams()
  if (tradingMode) params.append('trading_mode', tradingMode)
  const query = params.toString()
  const response = await apiRequest(`/arena/check-pnl-status${query ? `?${query}` : ''}`)
  return response.json()
}

export interface ArenaModelChatEntry {
  id: number
  account_id: number
  account_name: string
  model?: string | null
  operation: string
  symbol?: string | null
  reason: string
  executed: boolean
  prev_portion: number
  target_portion: number
  total_balance: number
  order_id?: number | null
  decision_time?: string | null
  trigger_mode?: StrategyTriggerMode | null
  strategy_enabled?: boolean
  last_trigger_at?: string | null
  trigger_latency_seconds?: number | null
  prompt_snapshot?: string | null
  reasoning_snapshot?: string | null
  decision_snapshot?: string | null
  wallet_address?: string | null
  signal_trigger_id?: number | null
  prompt_template_id?: number | null
  prompt_template_name?: string | null
  exchange?: string
}

export interface ArenaModelChatResponse {
  generated_at: string
  entries: ArenaModelChatEntry[]
}

export async function getArenaModelChat(params?: { limit?: number; account_id?: number; trading_mode?: string; wallet_address?: string; before_time?: string; after_time?: string; operation?: string; symbol?: string; exchange?: string }): Promise<ArenaModelChatResponse> {
  const search = new URLSearchParams()
  if (params?.limit) search.append('limit', params.limit.toString())
  if (params?.account_id) search.append('account_id', params.account_id.toString())
  if (params?.trading_mode) search.append('trading_mode', params.trading_mode)
  if (params?.wallet_address) search.append('wallet_address', params.wallet_address)
  if (params?.before_time) search.append('before_time', params.before_time)
  if (params?.after_time) search.append('after_time', params.after_time)
  if (params?.operation) search.append('operation', params.operation)
  if (params?.symbol) search.append('symbol', params.symbol)
  if (params?.exchange) search.append('exchange', params.exchange)
  const query = search.toString()
  const response = await apiRequest(`/arena/model-chat${query ? `?${query}` : ''}`)
  return response.json()
}

export interface ModelChatSnapshots {
  id: number
  prompt_snapshot?: string | null
  reasoning_snapshot?: string | null
  decision_snapshot?: string | null
  error?: string
}

export async function getModelChatSnapshots(decisionId: number): Promise<ModelChatSnapshots> {
  const response = await apiRequest(`/arena/model-chat/${decisionId}/snapshots`)
  return response.json()
}

export interface ArenaPositionItem {
  id: number
  symbol: string
  name: string
  market: string
  side: string
  quantity: number
  avg_cost: number
  current_price: number
  notional: number
  current_value: number
  unrealized_pnl: number
  leverage?: number | null
  margin_used?: number | null
  return_on_equity?: number | null
  percentage?: number | null
  margin_mode?: string | null
  liquidation_px?: number | null
  max_leverage?: number | null
  leverage_type?: string | null
}

export interface ArenaPositionsAccount {
  account_id: number
  account_name: string
  model?: string | null
  environment?: string | null
  exchange?: string
  wallet_address?: string | null
  total_unrealized_pnl: number
  available_cash: number
  used_margin?: number | null
  positions: ArenaPositionItem[]
  total_assets: number
  initial_capital: number
  total_return?: number | null
  margin_usage_percent?: number | null
  margin_mode?: string | null
}

export interface ArenaPositionsResponse {
  generated_at: string
  accounts: ArenaPositionsAccount[]
}

export async function getArenaPositions(params?: { account_id?: number; trading_mode?: string }): Promise<ArenaPositionsResponse> {
  const search = new URLSearchParams()
  if (params?.account_id) search.append('account_id', params.account_id.toString())
  if (params?.trading_mode) search.append('trading_mode', params.trading_mode)
  const query = search.toString()
  const response = await apiRequest(`/arena/positions${query ? `?${query}` : ''}`)
  const data = await response.json()

  const accounts = Array.isArray(data.accounts)
    ? data.accounts.map((account: any) => ({
        account_id: Number(account.account_id),
        account_name: account.account_name ?? '',
        model: account.model ?? null,
        environment: account.environment ?? null,
        exchange: account.exchange ?? 'hyperliquid',
        wallet_address: account.wallet_address ?? null,
        total_unrealized_pnl: Number(account.total_unrealized_pnl ?? 0),
        available_cash: Number(account.available_cash ?? 0),
        positions_value: Number(account.positions_value ?? account.used_margin ?? 0),
        used_margin: account.used_margin !== undefined ? Number(account.used_margin) : null,
        total_assets: Number(account.total_assets ?? 0),
        initial_capital: Number(account.initial_capital ?? 0),
        total_return:
          account.total_return !== undefined && account.total_return !== null
            ? Number(account.total_return)
            : null,
        margin_usage_percent:
          account.margin_usage_percent !== undefined && account.margin_usage_percent !== null
            ? Number(account.margin_usage_percent)
            : null,
        margin_mode: account.margin_mode ?? null,
        positions: Array.isArray(account.positions)
          ? account.positions.map((pos: any, idx: number) => ({
              id: pos.id ?? idx,
              symbol: pos.symbol ?? '',
              name: pos.name ?? '',
              market: pos.market ?? '',
              side: pos.side ?? '',
              quantity: Number(pos.quantity ?? 0),
              avg_cost: Number(pos.avg_cost ?? 0),
              current_price: Number(pos.current_price ?? 0),
              notional: Number(pos.notional ?? 0),
              current_value: Number(pos.current_value ?? 0),
              unrealized_pnl: Number(pos.unrealized_pnl ?? 0),
              leverage:
                pos.leverage !== undefined && pos.leverage !== null
                  ? Number(pos.leverage)
                  : null,
              margin_used:
                pos.margin_used !== undefined && pos.margin_used !== null
                  ? Number(pos.margin_used)
                  : null,
              return_on_equity:
                pos.return_on_equity !== undefined && pos.return_on_equity !== null
                  ? Number(pos.return_on_equity)
                  : null,
              percentage:
                pos.percentage !== undefined && pos.percentage !== null
                  ? Number(pos.percentage)
                  : null,
              margin_mode: pos.margin_mode ?? null,
              liquidation_px:
                pos.liquidation_px !== undefined && pos.liquidation_px !== null
                  ? Number(pos.liquidation_px)
                  : null,
              max_leverage:
                pos.max_leverage !== undefined && pos.max_leverage !== null
                  ? Number(pos.max_leverage)
                  : null,
              leverage_type: pos.leverage_type ?? null,
            }))
          : [],
      }))
    : []

  return {
    generated_at: data.generated_at ?? new Date().toISOString(),
    accounts,
  }
}

export interface ArenaAnalyticsAccount {
  account_id: number
  account_name: string
  model?: string | null
  initial_capital: number
  current_cash: number
  positions_value: number
  total_assets: number
  total_pnl: number
  total_return_pct?: number | null
  total_fees: number
  trade_count: number
  total_volume: number
  first_trade_time?: string | null
  last_trade_time?: string | null
  biggest_gain: number
  biggest_loss: number
  win_rate?: number | null
  loss_rate?: number | null
  sharpe_ratio?: number | null
  balance_volatility: number
  decision_count: number
  executed_decisions: number
  decision_execution_rate?: number | null
  avg_target_portion?: number | null
  avg_decision_interval_minutes?: number | null
}

export interface ArenaAnalyticsSummary {
  total_assets: number
  total_pnl: number
  total_return_pct?: number | null
  total_fees: number
  total_volume: number
  average_sharpe_ratio?: number | null
}

export interface ArenaAnalyticsResponse {
  generated_at: string
  accounts: ArenaAnalyticsAccount[]
  summary: ArenaAnalyticsSummary
}

export async function getArenaAnalytics(params?: { account_id?: number }): Promise<ArenaAnalyticsResponse> {
  const search = new URLSearchParams()
  if (params?.account_id) search.append('account_id', params.account_id.toString())
  const query = search.toString()
  const response = await apiRequest(`/arena/analytics${query ? `?${query}` : ''}`)
  return response.json()
}
