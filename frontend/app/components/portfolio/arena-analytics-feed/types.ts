import {
  ArenaAccountMeta,
  ArenaAnalyticsAccount,
  ArenaAnalyticsSummary,
} from '@/lib/api'

export interface ArenaAnalyticsFeedProps {
  refreshKey?: number
  autoRefreshInterval?: number
  selectedAccount?: number | 'all'
  onSelectedAccountChange?: (accountId: number | 'all') => void
}

export type FeedTab = 'leaderboard' | 'summary' | 'advanced'

export const CACHE_STALE_MS = 45_000

export type CacheKey = string

export interface AnalyticsCacheEntry {
  accounts: ArenaAnalyticsAccount[]
  summary: ArenaAnalyticsSummary | null
  generatedAt: string | null
  accountsMeta: ArenaAccountMeta[]
  lastFetched: number
}

export const ANALYTICS_CACHE = new Map<CacheKey, AnalyticsCacheEntry>()
