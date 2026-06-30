import { apiRequest } from './apiClient'

export interface BuilderAuthorizationStatus {
  authorized: boolean
  max_fee: number
  required_fee: number
  builder_address: string
}

export interface UnauthorizedAccount {
  account_id: number
  account_name: string
  wallet_address: string
  max_fee: number
  required_fee: number
  error_message?: string
}

export interface CheckMainnetAccountsResponse {
  unauthorized_accounts: UnauthorizedAccount[]
}

export interface ApproveBuilderResponse {
  success: boolean
  message: string
  builder_address: string
  approved_fee: string
  result?: unknown
}

export interface DisableTradingResponse {
  success: boolean
  message: string
  account_id: number
  account_name: string
}

export async function checkBuilderAuthorization(walletAddress: string): Promise<BuilderAuthorizationStatus> {
  const response = await apiRequest(`/account/hyperliquid/check-builder-authorization?wallet_address=${walletAddress}`)
  return response.json()
}

export async function checkMainnetAccounts(): Promise<CheckMainnetAccountsResponse> {
  const response = await apiRequest('/account/hyperliquid/check-mainnet-accounts')
  return response.json()
}

export async function approveBuilder(accountId: number): Promise<ApproveBuilderResponse> {
  const response = await apiRequest(`/account/hyperliquid/approve-builder?account_id=${accountId}`, {
    method: 'POST'
  })
  return response.json()
}

export async function disableTrading(accountId: number): Promise<DisableTradingResponse> {
  const response = await apiRequest(`/account/${accountId}/disable-trading`, {
    method: 'POST'
  })
  return response.json()
}
