import { useEffect, useState, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  getHyperliquidBalance,
  getWalletRateLimit,
  getTradingStats,
  getBinanceTradingStats,
  getBinanceSummary,
  getBinanceDailyQuota,
} from '@/lib/hyperliquidApi'
import type { TradingStats } from '@/lib/hyperliquidApi'
import type { HyperliquidEnvironment } from '@/lib/types/hyperliquid'
import type { HyperliquidBalance } from '@/lib/types/hyperliquid'
import { useTradingMode } from '@/contexts/TradingModeContext'
import { formatDateTime } from '@/lib/dateTime'
import {
  getCachedData,
  setCachedData,
  getApiUsageCacheKey,
  getTradingStatsCacheKey,
  getCacheTimestamp,
} from '@/lib/cacheUtils'
import TraderDetailModal from './TraderDetailModal'
import AccountSummaryRow from './hyperliquid-summary/AccountSummaryRow'
import type {
  AccountBalance,
  HyperliquidMultiAccountSummaryProps,
  Position,
  RateLimitData,
} from './hyperliquid-summary/types'

export type { Position } from './hyperliquid-summary/types'

export default function HyperliquidMultiAccountSummary({
  accounts,
  refreshKey,
  selectedAccount = 'all',
  positions = [],
}: HyperliquidMultiAccountSummaryProps) {
  const { t } = useTranslation()
  const { tradingMode } = useTradingMode()
  const [accountBalances, setAccountBalances] = useState<AccountBalance[]>([])
  const [globalLastUpdate, setGlobalLastUpdate] = useState<string | null>(null)
  const [selectedTraderForModal, setSelectedTraderForModal] = useState<AccountBalance | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Filter accounts based on selectedAccount - memoized to prevent infinite loops
  const filteredAccounts = useMemo(() => {
    return selectedAccount === 'all'
      ? accounts
      : accounts.filter(acc => acc.account_id === selectedAccount)
  }, [accounts, selectedAccount])

  // Get environment string
  const environment: HyperliquidEnvironment =
    tradingMode === 'testnet' || tradingMode === 'mainnet' ? tradingMode : 'testnet'

  // Load balances first (fast), then async load API Usage and Trading Stats
  const loadAllBalances = useCallback(async () => {
    // Step 1: Load balances quickly with cached data
    const balanceResults = await Promise.allSettled(
      filteredAccounts.map(async (acc) => {
        const exchange = acc.exchange || 'hyperliquid'
        try {
          let balance: HyperliquidBalance | null = null
          let rateLimit: RateLimitData | null = null

          if (exchange === 'binance') {
            // Binance: use summary endpoint for balance + rate limit
            const summary = await getBinanceSummary(acc.account_id)
            balance = {
              totalEquity: summary.equity,
              availableBalance: summary.available_balance,
              usedMargin: summary.used_margin,
              marginUsagePercent: summary.margin_usage,
              unrealizedPnl: summary.unrealized_pnl,
              lastUpdated: summary.last_updated
                ? (typeof summary.last_updated === 'number'
                    ? new Date(summary.last_updated).toISOString()
                    : summary.last_updated)
                : new Date().toISOString(),
            } as HyperliquidBalance
            if (summary.rate_limit) {
              rateLimit = {
                cumVlm: 0,
                nRequestsUsed: summary.rate_limit.used_weight,
                nRequestsCap: summary.rate_limit.weight_cap,
                remaining: summary.rate_limit.remaining,
                usagePercent: summary.rate_limit.usage_percent,
                isOverLimit: summary.rate_limit.usage_percent >= 100,
              }
            }
          } else {
            balance = await getHyperliquidBalance(acc.account_id)
          }

          // Fetch daily quota for Binance mainnet accounts
          let quota = null
          if (exchange === 'binance' && environment === 'mainnet') {
            try {
              const quotaData = await getBinanceDailyQuota(acc.account_id)
              if (quotaData.limited) {
                quota = quotaData
              }
            } catch (e) { /* ignore quota fetch errors */ }
          }

          const apiUsageCacheKey = getApiUsageCacheKey(acc.account_id, environment, exchange)
          const statsCacheKey = getTradingStatsCacheKey(acc.account_id, environment, exchange)
          return {
            accountId: acc.account_id,
            accountName: acc.account_name,
            exchange,
            balance,
            error: null,
            loading: false,
            rateLimit: rateLimit || getCachedData<RateLimitData>(apiUsageCacheKey),
            rateLimitUpdated: rateLimit ? Date.now() : getCacheTimestamp(apiUsageCacheKey),
            tradingStats: getCachedData<TradingStats>(statsCacheKey),
            tradingStatsUpdated: getCacheTimestamp(statsCacheKey),
            quota,
          }
        } catch (error: any) {
          return {
            accountId: acc.account_id,
            accountName: acc.account_name,
            exchange,
            balance: null,
            error: error.message || 'Failed to load',
            loading: false,
            rateLimit: null,
            rateLimitUpdated: null,
            tradingStats: null,
            tradingStatsUpdated: null,
          }
        }
      })
    )

    const initialBalances: AccountBalance[] = balanceResults.map((result, index) => {
      if (result.status === 'fulfilled') return result.value
      return {
        accountId: filteredAccounts[index].account_id,
        accountName: filteredAccounts[index].account_name,
        exchange: filteredAccounts[index].exchange || 'hyperliquid',
        balance: null,
        error: 'Failed to load',
        loading: false,
        rateLimit: null,
        rateLimitUpdated: null,
        tradingStats: null,
        tradingStatsUpdated: null,
      }
    })

    setAccountBalances(initialBalances)

    // Update timestamp
    const latestUpdate = initialBalances
      .map((acc) => acc.balance?.lastUpdated)
      .filter((ts): ts is string => ts !== undefined)
      .sort()
      .reverse()[0]
    if (latestUpdate) setGlobalLastUpdate(formatDateTime(latestUpdate))

    // Step 2: Async load API Usage and Trading Stats for Hyperliquid accounts missing cache
    filteredAccounts.forEach(async (acc) => {
      // Skip Binance accounts - their rate limit is already loaded in Step 1
      if ((acc.exchange || 'hyperliquid') === 'binance') return

      const accExchange = acc.exchange || 'hyperliquid'
      const apiUsageCacheKey = getApiUsageCacheKey(acc.account_id, environment, accExchange)
      const statsCacheKey = getTradingStatsCacheKey(acc.account_id, environment, accExchange)
      let needsUpdate = false
      let newRateLimit = getCachedData<RateLimitData>(apiUsageCacheKey)
      let newRateLimitUpdated = getCacheTimestamp(apiUsageCacheKey)
      let newTradingStats = getCachedData<TradingStats>(statsCacheKey)
      let newTradingStatsUpdated = getCacheTimestamp(statsCacheKey)

      // Fetch API Usage if not cached
      if (!newRateLimit) {
        try {
          const res = await getWalletRateLimit(acc.account_id, environment)
          if (res.success && res.rateLimit) {
            newRateLimit = res.rateLimit
            setCachedData(apiUsageCacheKey, newRateLimit)
            newRateLimitUpdated = Date.now()
            needsUpdate = true
          }
        } catch (e) { /* ignore */ }
      }

      // Fetch Trading Stats if not cached
      if (!newTradingStats) {
        try {
          const res = accExchange === 'binance'
            ? await getBinanceTradingStats(acc.account_id, environment)
            : await getTradingStats(acc.account_id, environment)
          if (res.success && res.stats) {
            newTradingStats = res.stats
            setCachedData(statsCacheKey, newTradingStats)
            newTradingStatsUpdated = Date.now()
            needsUpdate = true
          }
        } catch (e) { /* ignore */ }
      }

      // Update state if new data fetched
      if (needsUpdate) {
        setAccountBalances(prev => prev.map(a =>
          (a.accountId === acc.account_id && a.exchange === (acc.exchange || 'hyperliquid'))
            ? { ...a, rateLimit: newRateLimit, rateLimitUpdated: newRateLimitUpdated, tradingStats: newTradingStats, tradingStatsUpdated: newTradingStatsUpdated }
            : a
        ))
      }
    })
  }, [filteredAccounts, environment])

  useEffect(() => {
    if (filteredAccounts.length === 0) {
      setAccountBalances([])
      return
    }

    // Only initialize with loading state on first load (when accountBalances is empty)
    const isFirstLoad = accountBalances.length === 0
    if (isFirstLoad) {
      setAccountBalances(
        filteredAccounts.map((acc) => ({
          accountId: acc.account_id,
          accountName: acc.account_name,
          exchange: acc.exchange || 'hyperliquid',
          balance: null,
          error: null,
          loading: true,
          rateLimit: null,
          rateLimitUpdated: null,
          tradingStats: null,
          tradingStatsUpdated: null,
        }))
      )
    }

    loadAllBalances()
  }, [filteredAccounts, tradingMode, refreshKey])

  // Get positions for a specific account and exchange
  const getAccountPositions = (accountId: number, exchange: string) => {
    return positions.filter(p => p.account_id === accountId && (p.exchange || 'hyperliquid') === exchange)
  }

  // Handle opening modal
  const handleViewDetails = (account: AccountBalance) => {
    setSelectedTraderForModal(account)
    setIsModalOpen(true)
  }

  if (tradingMode !== 'testnet' && tradingMode !== 'mainnet') {
    return null
  }

  if (filteredAccounts.length === 0) {
    return (
      <Card className="p-6">
        <div className="text-sm text-muted-foreground">
          {t('account.noAccountsConfigured', 'No Hyperliquid accounts configured')}
        </div>
      </Card>
    )
  }

  const isLoading = accountBalances.some((acc) => acc.loading)

  // Use horizontal scroll layout when 4+ accounts to prevent card cramping
  const accountCount = accountBalances.length
  const useScrollLayout = accountCount >= 4

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t('account.accountStatus', 'Account Status')}</h2>
        <Badge
          variant={environment === 'testnet' ? 'default' : 'destructive'}
          className="uppercase text-xs"
        >
          {environment}
        </Badge>
      </div>

      {globalLastUpdate && (
        <div className="text-xs text-muted-foreground -mt-2">
          {t('common.lastUpdate', 'Last update')}: {globalLastUpdate}
        </div>
      )}

      {/* Loading state - only show when no data yet */}
      {isLoading && accountBalances.every(a => !a.balance) && (
        <div className="text-sm text-muted-foreground">{t('account.loadingData', 'Loading account data...')}</div>
      )}

      {/* Account cards - scroll horizontally when 4+ accounts */}
      <div className={useScrollLayout
        ? 'flex gap-4 overflow-x-auto pb-2 snap-x snap-mandatory'
        : `grid gap-4 ${accountCount === 1 ? 'grid-cols-1' : accountCount === 2 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`
      }>
        {accountBalances.map((account) => (
          <AccountSummaryRow
            key={`${account.accountId}_${account.exchange}`}
            account={account}
            positions={getAccountPositions(account.accountId, account.exchange)}
            t={t}
            useScrollLayout={useScrollLayout}
            onViewDetails={handleViewDetails}
          />
        ))}
      </div>

      {/* Trader Detail Modal */}
      {selectedTraderForModal && (
        <TraderDetailModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          account={selectedTraderForModal}
          positions={getAccountPositions(selectedTraderForModal.accountId, selectedTraderForModal.exchange)}
          environment={environment}
        />
      )}

    </div>
  )
}
