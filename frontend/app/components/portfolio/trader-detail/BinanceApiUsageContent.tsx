import { Info } from 'lucide-react'
import type { AccountDetailTranslator, RateLimitData, UsageColorResolver } from './types'

interface BinanceApiUsageContentProps {
  rateLimit: RateLimitData
  getUsageColor: UsageColorResolver
  getUsageBarColor: UsageColorResolver
  t: AccountDetailTranslator
}

export default function BinanceApiUsageContent({
  rateLimit,
  getUsageColor,
  getUsageBarColor,
  t,
}: BinanceApiUsageContentProps) {
  return (
    <>
      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.weightUsed', 'Weight Used')}</div>
          <div className="font-bold">{rateLimit.nRequestsUsed.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.weightCap', 'Weight Cap')}</div>
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
      <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded p-3">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-blue-700 dark:text-blue-400">
            {t('accountDetail.binanceWeightInfo', 'Binance API weight resets every minute. Each API call consumes different weight.')}
          </div>
        </div>
      </div>
    </>
  )
}
