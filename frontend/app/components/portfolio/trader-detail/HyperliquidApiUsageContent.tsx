import { AlertTriangle, Info } from 'lucide-react'
import type { AccountDetailTranslator, RateLimitData, UsageColorResolver } from './types'

interface HyperliquidApiUsageContentProps {
  rateLimit: RateLimitData
  getUsageColor: UsageColorResolver
  getUsageBarColor: UsageColorResolver
  t: AccountDetailTranslator
}

export default function HyperliquidApiUsageContent({
  rateLimit,
  getUsageColor,
  getUsageBarColor,
  t,
}: HyperliquidApiUsageContentProps) {
  return (
    <>
      <div className="grid grid-cols-4 gap-3 text-sm">
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.cumulativeVolume', 'Cumulative Volume')}</div>
          <div className="font-bold">${rateLimit.cumVlm.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.requestsUsed', 'Requests Used')}</div>
          <div className="font-medium">{rateLimit.nRequestsUsed.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.requestsCap', 'Requests Cap')}</div>
          <div className="font-medium">{rateLimit.nRequestsCap.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.remaining', 'Remaining')}</div>
          <div className={`font-bold ${getUsageColor(rateLimit.usagePercent)}`}>
            {rateLimit.remaining.toLocaleString()}
          </div>
        </div>
      </div>
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-muted-foreground">{t('accountDetail.usage', 'Usage')}</span>
          <span className={getUsageColor(rateLimit.usagePercent)}>{rateLimit.usagePercent.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <div
            className={`h-full rounded-full ${getUsageBarColor(rateLimit.usagePercent)}`}
            style={{ width: `${Math.min(rateLimit.usagePercent, 100)}%` }}
          />
        </div>
      </div>
      {rateLimit.isOverLimit && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-red-700 dark:text-red-400">
            <strong>{t('accountDetail.quotaExceeded', 'API Quota Exceeded!')}</strong> {t('accountDetail.quotaExceededDesc', 'Order placement will fail. Trade more to increase quota.')}
          </div>
        </div>
      )}
      <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded p-3">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-blue-700 dark:text-blue-400">
            <strong>{t('accountDetail.increaseQuota', 'To increase quota:')}</strong> {t('accountDetail.increaseQuotaDesc', 'Complete more trades. Every $1 USDC traded adds 1 request to your cap.')}
          </div>
        </div>
      </div>
    </>
  )
}
