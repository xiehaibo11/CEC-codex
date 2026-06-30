import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/dateTime'
import BinanceApiUsageContent from './BinanceApiUsageContent'
import HyperliquidApiUsageContent from './HyperliquidApiUsageContent'
import type { AccountDetailTranslator, RateLimitData } from './types'

interface ApiUsageSectionProps {
  rateLimit: RateLimitData | null
  rateLimitUpdated: number | null
  refreshing: boolean
  onRefresh: () => void
  isBinance: boolean
  t: AccountDetailTranslator
}

function getUsageColor(percent: number) {
  if (percent >= 90) return 'text-red-600'
  if (percent >= 70) return 'text-yellow-600'
  return 'text-green-600'
}

function getUsageBarColor(percent: number) {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 70) return 'bg-yellow-500'
  return 'bg-green-500'
}

export default function ApiUsageSection({
  rateLimit,
  rateLimitUpdated,
  refreshing,
  onRefresh,
  isBinance,
  t,
}: ApiUsageSectionProps) {
  return (
    <div className="border rounded-lg p-4 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">
          {isBinance ? t('accountDetail.apiWeight', 'API Weight (per minute)') : t('accountDetail.apiUsage', 'API Usage')}
        </h3>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={refreshing}>
          <RefreshCw className={`w-3 h-3 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
          {t('common.refresh', 'Refresh')}
        </Button>
      </div>

      {rateLimit ? (
        <div className="space-y-3">
          {isBinance ? (
            <BinanceApiUsageContent
              rateLimit={rateLimit}
              getUsageColor={getUsageColor}
              getUsageBarColor={getUsageBarColor}
              t={t}
            />
          ) : (
            <HyperliquidApiUsageContent
              rateLimit={rateLimit}
              getUsageColor={getUsageColor}
              getUsageBarColor={getUsageBarColor}
              t={t}
            />
          )}

          {rateLimitUpdated && (
            <div className="text-xs text-muted-foreground text-right">
              {t('accountDetail.lastUpdated', 'Last updated')}: {formatDateTime(new Date(rateLimitUpdated))}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">{t('accountDetail.clickRefreshApi', 'Click Refresh to load API usage data')}</div>
      )}
    </div>
  )
}
