import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { getWalletRateLimit, getTradingStats, getBinanceTradingStats, TradingStats, getBinanceRateLimit } from '@/lib/hyperliquidApi'
import { setCachedData, getCachedData, getCacheTimestamp, getApiUsageCacheKey, getTradingStatsCacheKey } from '@/lib/cacheUtils'
import type { HyperliquidBalance } from '@/lib/types/hyperliquid'
import type { HyperliquidEnvironment } from '@/lib/types/hyperliquid'
import type { Position } from './HyperliquidMultiAccountSummary'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import AccountStatusSection from './trader-detail/AccountStatusSection'
import ApiUsageSection from './trader-detail/ApiUsageSection'
import TradingStatsSection from './trader-detail/TradingStatsSection'
import PositionsSection from './trader-detail/PositionsSection'
import type { RateLimitData } from './trader-detail/types'

interface AccountData {
  accountId: number
  accountName: string
  exchange: string
  balance: HyperliquidBalance | null
  rateLimit: RateLimitData | null
  rateLimitUpdated: number | null
  tradingStats: TradingStats | null
  tradingStatsUpdated: number | null
}

interface TraderDetailModalProps {
  isOpen: boolean
  onClose: () => void
  account: AccountData
  positions: Position[]
  environment: HyperliquidEnvironment
}

export default function TraderDetailModal({
  isOpen,
  onClose,
  account,
  positions,
  environment,
}: TraderDetailModalProps) {
  const { t } = useTranslation()
  // Initialize state from props (which already contain cached data)
  const [rateLimit, setRateLimit] = useState<RateLimitData | null>(account.rateLimit)
  const [rateLimitUpdated, setRateLimitUpdated] = useState<number | null>(account.rateLimitUpdated)
  const [tradingStats, setTradingStats] = useState<TradingStats | null>(account.tradingStats)
  const [tradingStatsUpdated, setTradingStatsUpdated] = useState<number | null>(account.tradingStatsUpdated)
  const [refreshingRateLimit, setRefreshingRateLimit] = useState(false)
  const [refreshingStats, setRefreshingStats] = useState(false)

  const isBinance = (account.exchange || 'hyperliquid') === 'binance'
  const accountExchange = account.exchange || 'hyperliquid'

  // When modal opens, read latest data from cache (fixes stale data after refresh)
  useEffect(() => {
    if (isOpen) {
      // Read from cache first (may have been updated by previous refresh)
      const cachedRateLimit = getCachedData<RateLimitData>(getApiUsageCacheKey(account.accountId, environment, accountExchange))
      const cachedStats = getCachedData<TradingStats>(getTradingStatsCacheKey(account.accountId, environment, accountExchange))

      setRateLimit(cachedRateLimit || account.rateLimit)
      setRateLimitUpdated(cachedRateLimit ? getCacheTimestamp(getApiUsageCacheKey(account.accountId, environment, accountExchange)) : account.rateLimitUpdated)
      setTradingStats(cachedStats || account.tradingStats)
      setTradingStatsUpdated(cachedStats ? getCacheTimestamp(getTradingStatsCacheKey(account.accountId, environment, accountExchange)) : account.tradingStatsUpdated)
    }
  }, [isOpen, account.accountId, environment, accountExchange])

  // Refresh API Usage
  const handleRefreshRateLimit = async () => {
    setRefreshingRateLimit(true)
    try {
      if (isBinance) {
        const res = await getBinanceRateLimit(account.accountId)
        if (res.success && res.rate_limit) {
          const rl: RateLimitData = {
            cumVlm: 0,
            nRequestsUsed: res.rate_limit.used_weight,
            nRequestsCap: res.rate_limit.weight_cap,
            remaining: res.rate_limit.remaining,
            usagePercent: res.rate_limit.usage_percent,
            isOverLimit: res.rate_limit.usage_percent >= 100,
          }
          setRateLimit(rl)
          setRateLimitUpdated(Date.now())
          setCachedData(getApiUsageCacheKey(account.accountId, environment, accountExchange), rl)
          toast.success('API weight updated')
        }
      } else {
        const res = await getWalletRateLimit(account.accountId, environment)
        if (res.success && res.rateLimit) {
          setRateLimit(res.rateLimit)
          setRateLimitUpdated(Date.now())
          setCachedData(getApiUsageCacheKey(account.accountId, environment, accountExchange), res.rateLimit)
          toast.success('API usage updated')
        }
      }
    } catch (e) {
      toast.error('Failed to refresh API usage')
    } finally {
      setRefreshingRateLimit(false)
    }
  }

  // Refresh Trading Stats
  const handleRefreshStats = async () => {
    setRefreshingStats(true)
    try {
      const res = isBinance
        ? await getBinanceTradingStats(account.accountId, environment)
        : await getTradingStats(account.accountId, environment)
      if (res.success && res.stats) {
        setTradingStats(res.stats)
        setTradingStatsUpdated(Date.now())
        setCachedData(getTradingStatsCacheKey(account.accountId, environment, accountExchange), res.stats)
        toast.success('Trading stats updated')
      }
    } catch (e) {
      toast.error('Failed to refresh trading stats')
    } finally {
      setRefreshingStats(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>{account.accountName} - {t('accountDetail.details', 'Details')}</span>
            <img
              src={isBinance ? '/static/binance_logo.svg' : '/static/hyperliquid_logo.svg'}
              alt={isBinance ? 'Binance' : 'Hyperliquid'}
              className="h-4 w-4"
            />
            <Badge variant={environment === 'testnet' ? 'default' : 'destructive'} className="uppercase text-xs">
              {environment}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Account Status Section */}
          {account.balance && (
            <AccountStatusSection balance={account.balance} isBinance={isBinance} t={t} />
          )}

          {/* API Usage Section */}
          <ApiUsageSection
            rateLimit={rateLimit}
            rateLimitUpdated={rateLimitUpdated}
            refreshing={refreshingRateLimit}
            onRefresh={handleRefreshRateLimit}
            isBinance={isBinance}
            t={t}
          />

          {/* Trading Stats Section */}
          <TradingStatsSection
            stats={tradingStats}
            statsUpdated={tradingStatsUpdated}
            refreshing={refreshingStats}
            onRefresh={handleRefreshStats}
            t={t}
          />

          {/* Positions Section */}
          <PositionsSection positions={positions} t={t} />
        </div>
      </DialogContent>
    </Dialog>
  )
}
