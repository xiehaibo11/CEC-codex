import { apiRequest } from './apiClient'

export interface User {
  id: number
  username: string
  email?: string
  is_active: boolean
}

export interface UserAuthResponse {
  user: User
  session_token: string
  expires_at: string
}

export interface TradingAccount {
  id: number
  user_id: number
  name: string
  model?: string
  base_url?: string
  api_key?: string
  initial_capital: number
  current_cash: number
  frozen_cash: number
  account_type: string
  is_active: boolean
  auto_trading_enabled?: boolean
  wallet_address?: string | null
  has_mainnet_wallet?: boolean
  show_on_dashboard?: boolean
  avatar_preset_id?: number | null
}

export interface TradingAccountCreate {
  name: string
  model?: string
  base_url?: string
  api_key?: string
  initial_capital?: number
  account_type?: string
  auto_trading_enabled?: boolean
}

export interface TradingAccountUpdate {
  name?: string
  model?: string
  base_url?: string
  api_key?: string
  auto_trading_enabled?: boolean
}

export type StrategyTriggerMode = 'realtime' | 'interval' | 'tick_batch'

export interface StrategyConfig {
  trigger_mode: StrategyTriggerMode
  interval_seconds?: number | null
  tick_batch_size?: number | null
  enabled: boolean
  last_trigger_at?: string | null
  exchange?: string
}

export interface StrategyConfigUpdate {
  trigger_mode: StrategyTriggerMode
  interval_seconds?: number | null
  tick_batch_size?: number | null
  enabled: boolean
}

export async function loginUser(username: string, password: string): Promise<UserAuthResponse> {
  const response = await apiRequest('/users/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  return response.json()
}

export async function getUserProfile(sessionToken: string): Promise<User> {
  const response = await apiRequest(`/users/profile?session_token=${sessionToken}`)
  return response.json()
}

export async function getAccountStrategy(accountId: number): Promise<StrategyConfig> {
  const response = await apiRequest(`/account/${accountId}/strategy`)
  return response.json()
}

export async function updateAccountStrategy(accountId: number, config: StrategyConfigUpdate): Promise<StrategyConfig> {
  const response = await apiRequest(`/account/${accountId}/strategy`, {
    method: 'PUT',
    body: JSON.stringify(config),
  })
  return response.json()
}

export async function getAccounts(options?: { include_hidden?: boolean }): Promise<TradingAccount[]> {
  const params = new URLSearchParams()
  if (options?.include_hidden) {
    params.set('include_hidden', 'true')
  }
  const queryString = params.toString()
  const url = queryString ? `/account/list?${queryString}` : '/account/list'
  const response = await apiRequest(url)
  return response.json()
}

export interface DashboardVisibilityUpdate {
  account_id: number
  show_on_dashboard: boolean
}

export async function updateDashboardVisibility(
  updates: DashboardVisibilityUpdate[]
): Promise<{ success: boolean; updated_count: number; updates: DashboardVisibilityUpdate[] }> {
  const response = await apiRequest('/account/dashboard-visibility', {
    method: 'PATCH',
    body: JSON.stringify(updates)
  })
  return response.json()
}

export interface HyperAiProfile {
  llm_configured: boolean
  llm_provider?: string | null
  llm_model?: string | null
  llm_base_url?: string | null
}

export async function getHyperAiProfile(): Promise<HyperAiProfile> {
  const response = await apiRequest('/hyper-ai/profile')
  return response.json()
}

export async function getOverview(): Promise<any> {
  const response = await apiRequest('/account/overview')
  return response.json()
}

export async function createAccount(account: TradingAccountCreate): Promise<TradingAccount> {
  const response = await apiRequest('/account/', {
    method: 'POST',
    body: JSON.stringify({
      name: account.name,
      model: account.model,
      base_url: account.base_url,
      api_key: account.api_key,
      account_type: account.account_type || 'AI',
      initial_capital: account.initial_capital || 10000,
      auto_trading_enabled: account.auto_trading_enabled ?? true,
    })
  })
  return response.json()
}

export async function updateAccount(accountId: number, account: TradingAccountUpdate): Promise<TradingAccount> {
  const response = await apiRequest(`/account/${accountId}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: account.name,
      model: account.model,
      base_url: account.base_url,
      api_key: account.api_key,
      auto_trading_enabled: account.auto_trading_enabled,
    })
  })
  return response.json()
}

export async function testLLMConnection(testData: {
  model?: string;
  base_url?: string;
  api_key?: string;
}): Promise<{ success: boolean; message: string; response?: any }> {
  const response = await apiRequest('/account/test-llm', {
    method: 'POST',
    body: JSON.stringify(testData)
  })
  return response.json()
}

export type AIAccount = TradingAccount
export type AIAccountCreate = TradingAccountCreate

export const listAIAccounts = () => getAccounts()
export const createAIAccount = (account: any) => {
  console.warn("createAIAccount is deprecated. Use default mode or new trading account APIs.")
  return Promise.resolve({} as TradingAccount)
}
export const updateAIAccount = (id: number, account: any) => {
  console.warn("updateAIAccount is deprecated. Use default mode or new trading account APIs.")
  return Promise.resolve({} as TradingAccount)
}
export const deleteAIAccount = (id: number) => {
  console.warn("deleteAIAccount is deprecated. Use default mode or new trading account APIs.")
  return Promise.resolve()
}
