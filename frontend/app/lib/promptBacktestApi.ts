import { apiRequest } from './apiClient'

export interface BacktestItemInput {
  decision_log_id: number
  modified_prompt: string
}

export interface ReplaceRule {
  find: string
  replace: string
}

export interface CreateBacktestTaskRequest {
  account_id: number
  name?: string
  items: BacktestItemInput[]
  replace_rules?: ReplaceRule[]
}

export interface BacktestTask {
  id: number
  account_id: number
  name: string | null
  status: string
  total_count: number
  completed_count: number
  failed_count: number
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface BacktestResultItem {
  id: number
  original_decision_time: string | null
  original_operation: string | null
  original_symbol: string | null
  original_target_portion: number | null
  original_realized_pnl: number | null
  new_operation: string | null
  new_symbol: string | null
  new_target_portion: number | null
  decision_changed: boolean | null
  change_type: string | null
  status: string
}

export interface BacktestResultSummary {
  total: number
  completed: number
  failed: number
  changed: number
  unchanged: number
  avoided_loss_count: number
  avoided_loss_amount: number
  missed_profit_count: number
  missed_profit_amount: number
}

export interface BacktestItemDetail {
  id: number
  original_operation: string | null
  original_symbol: string | null
  original_reasoning: string | null
  original_decision_json: string | null
  original_prompt_template_name: string | null
  modified_prompt: string | null
  new_operation: string | null
  new_symbol: string | null
  new_reasoning: string | null
  new_decision_json: string | null
  decision_changed: boolean | null
  change_type: string | null
  error_message: string | null
}

export async function createBacktestTask(request: CreateBacktestTaskRequest) {
  const response = await apiRequest('/prompt-backtest/tasks', {
    method: 'POST',
    body: JSON.stringify(request)
  })
  return response.json()
}

export async function listBacktestTasks(accountId?: number, limit: number = 20) {
  const params = new URLSearchParams()
  if (accountId) params.append('account_id', String(accountId))
  params.append('limit', String(limit))
  const response = await apiRequest(`/prompt-backtest/tasks?${params}`)
  return response.json() as Promise<{ tasks: BacktestTask[] }>
}

export async function getBacktestTaskStatus(taskId: number) {
  const response = await apiRequest(`/prompt-backtest/tasks/${taskId}`)
  return response.json() as Promise<BacktestTask>
}

export async function getBacktestTaskResults(taskId: number) {
  const response = await apiRequest(`/prompt-backtest/tasks/${taskId}/results`)
  return response.json() as Promise<{
    task: BacktestTask
    items: BacktestResultItem[]
    summary: BacktestResultSummary
  }>
}

export async function getBacktestItemDetail(itemId: number) {
  const response = await apiRequest(`/prompt-backtest/items/${itemId}`)
  return response.json() as Promise<BacktestItemDetail>
}

export async function deleteBacktestTask(taskId: number) {
  const response = await apiRequest(`/prompt-backtest/tasks/${taskId}`, {
    method: 'DELETE'
  })
  return response.json()
}

export async function retryBacktestTask(taskId: number) {
  const response = await apiRequest(`/prompt-backtest/tasks/${taskId}/retry`, {
    method: 'POST'
  })
  return response.json() as Promise<{
    success: boolean
    message: string
    retry_count: number
  }>
}

export interface BacktestTaskItemForImport {
  id: number
  modified_prompt: string
  operation: string | null
  symbol: string | null
  reason: string | null
  decision_time: string | null
  realized_pnl: number | null
}

export async function getBacktestTaskItems(taskId: number) {
  const response = await apiRequest(`/prompt-backtest/tasks/${taskId}/items`)
  return response.json() as Promise<{
    task_id: number
    task_name: string
    items: BacktestTaskItemForImport[]
  }>
}
