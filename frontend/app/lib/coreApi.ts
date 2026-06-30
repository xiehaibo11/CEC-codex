import { apiRequest } from './apiClient'

export async function checkRequiredConfigs() {
  const response = await apiRequest('/config/check-required')
  return response.json()
}

export async function getCryptoSymbols() {
  const response = await apiRequest('/crypto/symbols')
  return response.json()
}

export async function getCryptoPrice(symbol: string) {
  const response = await apiRequest(`/crypto/price/${symbol}`)
  return response.json()
}

export async function getCryptoMarketStatus(symbol: string) {
  const response = await apiRequest(`/crypto/status/${symbol}`)
  return response.json()
}

export async function getPopularCryptos() {
  const response = await apiRequest('/crypto/popular')
  return response.json()
}

export interface AIDecision {
  id: number
  account_id: number
  decision_time: string
  reason: string
  operation: string
  symbol?: string
  prev_portion: number
  target_portion: number
  total_balance: number
  executed: string
  order_id?: number
}

export interface AIDecisionFilters {
  operation?: string
  symbol?: string
  executed?: boolean
  start_date?: string
  end_date?: string
  limit?: number
}

export async function getAIDecisions(accountId: number, filters?: AIDecisionFilters): Promise<AIDecision[]> {
  const params = new URLSearchParams()
  if (filters?.operation) params.append('operation', filters.operation)
  if (filters?.symbol) params.append('symbol', filters.symbol)
  if (filters?.executed !== undefined) params.append('executed', filters.executed.toString())
  if (filters?.start_date) params.append('start_date', filters.start_date)
  if (filters?.end_date) params.append('end_date', filters.end_date)
  if (filters?.limit) params.append('limit', filters.limit.toString())

  const queryString = params.toString()
  const endpoint = `/accounts/${accountId}/ai-decisions${queryString ? `?${queryString}` : ''}`

  const response = await apiRequest(endpoint)
  return response.json()
}

export async function getAIDecisionById(accountId: number, decisionId: number): Promise<AIDecision> {
  const response = await apiRequest(`/accounts/${accountId}/ai-decisions/${decisionId}`)
  return response.json()
}

export async function getAIDecisionStats(accountId: number, days?: number): Promise<{
  total_decisions: number
  executed_decisions: number
  execution_rate: number
  operations: { [key: string]: number }
  avg_target_portion: number
}> {
  const params = days ? `?days=${days}` : ''
  const response = await apiRequest(`/accounts/${accountId}/ai-decisions/stats${params}`)
  return response.json()
}
