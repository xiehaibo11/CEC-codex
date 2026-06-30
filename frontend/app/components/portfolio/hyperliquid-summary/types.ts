import type { TradingStats } from '@/lib/hyperliquidApi'
import type { HyperliquidBalance } from '@/lib/types/hyperliquid'

export interface Position {
  symbol: string
  side: string
  size: number
  entry_price: number
  mark_price: number
  unrealized_pnl: number
  leverage: number
  account_id: number
  exchange?: string // 'hyperliquid' | 'binance'
}

export interface RateLimitData {
  cumVlm: number
  nRequestsUsed: number
  nRequestsCap: number
  remaining: number
  usagePercent: number
  isOverLimit: boolean
}

export interface AccountBalance {
  accountId: number
  accountName: string
  exchange: string
  balance: HyperliquidBalance | null
  error: string | null
  loading: boolean
  rateLimit: RateLimitData | null
  rateLimitUpdated: number | null
  tradingStats: TradingStats | null
  tradingStatsUpdated: number | null
  quota?: {
    limited: boolean
    used: number
    limit: number
    remaining: number
    reset_at?: number
  } | null
}

export interface HyperliquidMultiAccountSummaryProps {
  accounts: Array<{ account_id: number; account_name: string; exchange?: string }>
  refreshKey?: number
  selectedAccount?: number | 'all'
  positions?: Position[]
}

export type SummaryTranslator = (key: string, fallback?: string) => string
