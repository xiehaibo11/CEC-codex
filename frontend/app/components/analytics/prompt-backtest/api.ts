import type { ModelChatEntry } from './types'

export const PAGE_SIZE = 100

interface FetchRecordsParams {
  accountId: string
  tradingMode: string
  exchange: string
  beforeTime?: string
}

// Fetch model chat records (without snapshots for performance)
export async function fetchModelChatRecords({
  accountId,
  tradingMode,
  exchange,
  beforeTime,
}: FetchRecordsParams): Promise<ModelChatEntry[]> {
  const params = new URLSearchParams()
  params.append('account_id', accountId)
  params.append('limit', String(PAGE_SIZE))
  // Don't include snapshots in list - load them when adding to workspace
  if (tradingMode !== 'all') {
    params.append('trading_mode', tradingMode)
  }
  if (exchange !== 'all') {
    params.append('exchange', exchange)
  }
  if (beforeTime) {
    params.append('before_time', beforeTime)
  }

  const response = await fetch(`/api/arena/model-chat?${params}`)
  const data = await response.json()
  return data.entries || []
}

// Fetch snapshots for the given record ids
export async function fetchModelChatSnapshots(
  accountId: string,
  ids: number[]
): Promise<ModelChatEntry[]> {
  const params = new URLSearchParams()
  params.append('account_id', accountId)
  params.append('ids', ids.join(','))
  params.append('include_snapshots', 'true')

  const response = await fetch(`/api/arena/model-chat?${params}`)
  const data = await response.json()
  return data.entries || []
}
