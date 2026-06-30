import type { ReplayKlineData, TradeReplayData } from './types'

const API_BASE = '/api/analytics'

export async function fetchTradeReplayData(id: number): Promise<TradeReplayData> {
  const res = await fetch(`${API_BASE}/trades/${id}/replay`)
  if (!res.ok) throw new Error('Failed to load replay data')
  return res.json()
}

export async function fetchReplayKlineData(
  tradeId: number,
  period: string
): Promise<ReplayKlineData> {
  const response = await fetch(`/api/analytics/trades/${tradeId}/kline?period=${period}`)
  if (!response.ok) {
    const errData = await response.json().catch(() => ({}))
    throw new Error(errData.detail || 'Failed to fetch kline data')
  }
  return response.json()
}
