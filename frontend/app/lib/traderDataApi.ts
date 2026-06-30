import { apiRequest } from './apiClient'

export interface TraderExportData {
  account_id: number
  account_name: string
  exported_at: string
  decision_logs: Array<{
    symbol: string
    decision_time: string
    operation: string
    reason?: string
    prev_portion?: number
    target_portion?: number
    total_balance?: number
    executed?: string
    prompt_snapshot?: string
    reasoning_snapshot?: string
    decision_snapshot?: string
    hyperliquid_environment?: string
    wallet_address?: string
    hyperliquid_order_id?: string
    tp_order_id?: string
    sl_order_id?: string
    realized_pnl?: number
    pnl_updated_at?: string
  }>
  trades: Array<{
    environment: string
    wallet_address: string
    symbol: string
    side: string
    quantity: number
    price: number
    leverage: number
    order_id: string
    trade_value: number
    fee: number
    trade_time: string
  }>
}

export interface ImportPreviewResponse {
  will_import: {
    decision_logs: number
    trades: number
  }
  will_skip: {
    decision_logs: number
    trades: number
  }
  details: {
    new_decision_times: string[]
    duplicate_decision_times: string[]
    new_trade_ids: string[]
    duplicate_trade_ids: string[]
  }
}

export interface ImportExecuteResponse {
  success: boolean
  imported: {
    decision_logs: number
    trades: number
  }
  skipped: {
    decision_logs: number
    trades: number
  }
  errors: string[]
}

export async function exportTraderData(accountId: number): Promise<TraderExportData> {
  const response = await apiRequest(`/trader/${accountId}/export`)
  return response.json()
}

export async function previewTraderImport(
  accountId: number,
  data: TraderExportData
): Promise<ImportPreviewResponse> {
  const response = await apiRequest(`/trader/${accountId}/import/preview`, {
    method: 'POST',
    body: JSON.stringify({ data })
  })
  return response.json()
}

export async function executeTraderImport(
  accountId: number,
  data: TraderExportData,
  confirmed: boolean = true
): Promise<ImportExecuteResponse> {
  const response = await apiRequest(`/trader/${accountId}/import/execute`, {
    method: 'POST',
    body: JSON.stringify({ data, confirmed })
  })
  return response.json()
}
