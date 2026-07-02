import type { MutableRefObject } from 'react'

export interface AssetCurveData {
  timestamp?: number
  datetime_str?: string
  date?: string
  account_id: number
  total_assets: number
  cash: number
  positions_value: number
  is_initial?: boolean
  user_id: number
  username: string
}

export interface AssetCurveProps {
  data?: AssetCurveData[]
  wsRef?: MutableRefObject<WebSocket | null>
  highlightAccountId?: number | 'all'
  onHighlightAccountChange?: (accountId: number | 'all') => void
}

export type Timeframe = '5m' | '1h' | '1d'

export const DEFAULT_TIMEFRAME: Timeframe = '5m'
export const CACHE_STALE_MS = 45_000

export interface TimeframeCacheEntry {
  data: AssetCurveData[]
  lastFetched: number
  initialized: boolean
}

export interface LogoAsset {
  src: string
  alt: string
  color?: string
}

export interface ChartPoint {
  timestamp: string
  formattedTime: string
  [username: string]: string | number | null
}

export interface AccountSummary {
  username: string
  assets: number
  accountId?: number
  logo?: LogoAsset
}

export interface AccountMeta {
  accountId?: number
  color: string
  logo?: LogoAsset
}

export interface BaseProcessedAssetCurve {
  chartData: ChartPoint[]
  accountSummaries: AccountSummary[]
  uniqueUsers: string[]
  userAccountMap: Map<string, number | undefined>
}

export interface ProcessedAssetCurve {
  chartData: ChartPoint[]
  accountSummaries: AccountSummary[]
  uniqueUsers: string[]
  rankedAccounts: AccountSummary[]
}
