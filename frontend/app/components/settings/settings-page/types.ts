import type { Dispatch, SetStateAction } from 'react'
import type { TFunction } from 'i18next'
import type {
  BinanceSymbolMeta,
  NewsSourceConfig,
  NewsStatsResponse,
  TestNewsSourceResponse,
} from '@/lib/api'

export interface StorageStats {
  exchange: string
  total_size_mb: number
  tables: Record<string, number>
  retention_days: number
  symbol_count: number
  estimated_per_symbol_per_day_mb: number
}

export interface BackfillStatus {
  status: string
  progress: number
  task_id?: number
  symbols?: string[]
  error_message?: string
}

export type NewsSourceAdapter = 'rss_generic' | 'cryptopanic' | 'finnhub_calendar'

export interface WatchlistSettingsTabProps {
  t: TFunction
  availableSymbols: BinanceSymbolMeta[]
  watchlistSymbols: string[]
  maxSymbols: number
  loading: boolean
  saving: boolean
  error: string | null
  success: string | null
  searchQuery: string
  onSearchQueryChange: (value: string) => void
  onToggleSymbol: (symbol: string) => void
  onSave: () => void
}

export interface BinanceDataSettingsTabProps {
  t: TFunction
  watchlistSymbols: string[]
  storageStats: Record<string, StorageStats>
  storageLoading: boolean
  retentionDays: Record<string, string>
  setRetentionDays: Dispatch<SetStateAction<Record<string, string>>>
  retentionSaving: boolean
  retentionError: string | null
  retentionSuccess: string | null
  backfillStatus: Record<string, BackfillStatus>
  backfillStarting: Record<string, boolean>
  backfillJustCompleted: Record<string, boolean>
  onSaveRetention: () => void
  onStartBackfill: (exchange: string, force?: boolean) => void
}

export interface NewsSourcesSettingsTabProps {
  t: TFunction
  newsSources: NewsSourceConfig[]
  newsStats: NewsStatsResponse | null
  newsLoading: boolean
  newsSaving: boolean
  newsError: string | null
  newsSuccess: string | null
  enabledNewsSourceCount: number
  hasUnsavedNewsSources: boolean
  newsCountsByDomain: Record<string, number>
  newsFormAdapter: NewsSourceAdapter
  newsTestUrl: string
  newsFormInterval: string
  newsFormAuthToken: string
  newsFormApiKey: string
  newsTesting: boolean
  newsTestError: string | null
  newsTestResult: TestNewsSourceResponse | null
  formatDateTime: (value?: string | null) => string
  extractDomain: (url: string) => string
  onToggleNewsSource: (index: number, enabled: boolean) => void
  onSaveNewsSources: () => void
  onRefreshNewsSources: () => void
  onNewsSourceIntervalChange: (index: number, value: string) => void
  onNewsFormAdapterChange: (value: NewsSourceAdapter) => void
  onNewsFormIntervalChange: (value: string) => void
  onNewsFormAuthTokenChange: (value: string) => void
  onNewsFormApiKeyChange: (value: string) => void
  onNewsTestUrlChange: (value: string) => void
  onTestNewsSource: () => void
  onAddNewsSource: () => void
}
