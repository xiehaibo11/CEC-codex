import { apiRequest } from '@/lib/api'
import type {
  Account,
  DimensionResponse,
  EventContractAttributionResponse,
  SummaryResponse,
  TradesResponse,
} from './types'

const API_BASE = '/api/analytics'

export async function fetchSummary(params: URLSearchParams): Promise<SummaryResponse> {
  const res = await fetch(`${API_BASE}/summary?${params}`)
  if (!res.ok) throw new Error('Failed to fetch summary')
  return res.json()
}

export async function fetchByDimension(dimension: string, params: URLSearchParams): Promise<DimensionResponse> {
  const res = await fetch(`${API_BASE}/by-${dimension}?${params}`)
  if (!res.ok) throw new Error(`Failed to fetch by-${dimension}`)
  return res.json()
}

export async function fetchProgramByDimension(dimension: string, params: URLSearchParams): Promise<DimensionResponse> {
  const res = await fetch(`${API_BASE}/program-by-${dimension}?${params}`)
  if (!res.ok) throw new Error(`Failed to fetch program-by-${dimension}`)
  return res.json()
}

export async function fetchAccounts(): Promise<Account[]> {
  const res = await apiRequest('/account/list')
  if (!res.ok) throw new Error('Failed to fetch accounts')
  const data = await res.json()
  return data.map((acc: { id: number; name: string; account_type: string; model?: string }) => ({
    id: acc.id,
    name: acc.name,
    account_type: acc.account_type,
    model: acc.model,
  }))
}

export async function fetchTrades(params: URLSearchParams): Promise<TradesResponse> {
  const res = await fetch(`${API_BASE}/trades?${params}`)
  if (!res.ok) throw new Error('Failed to fetch trades')
  return res.json()
}

export async function getEventContractAttribution(params?: {
  trader_id?: number
  start_date?: string
  end_date?: string
}): Promise<EventContractAttributionResponse> {
  const query = new URLSearchParams()
  if (params?.trader_id !== undefined) query.set('trader_id', String(params.trader_id))
  if (params?.start_date) query.set('start_date', params.start_date)
  if (params?.end_date) query.set('end_date', params.end_date)
  const qs = query.toString()
  const res = await fetch(`${API_BASE}/event-contract${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error('Failed to fetch event contract attribution')
  return res.json()
}
