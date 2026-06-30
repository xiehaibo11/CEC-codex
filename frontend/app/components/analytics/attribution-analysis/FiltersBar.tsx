import { useTranslation } from 'react-i18next'
import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Account } from './types'

interface FiltersBarProps {
  timeRange: string
  onTimeRangeChange: (value: string) => void
  exchange: string
  onExchangeChange: (value: string) => void
  environment: string
  onEnvironmentChange: (value: string) => void
  accountId: string
  onAccountIdChange: (value: string) => void
  accounts: Account[]
  onOpenAiChat: () => void
}

export default function FiltersBar({
  timeRange,
  onTimeRangeChange,
  exchange,
  onExchangeChange,
  environment,
  onEnvironmentChange,
  accountId,
  onAccountIdChange,
  accounts,
  onOpenAiChat,
}: FiltersBarProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-wrap gap-4 items-center justify-between">
      <div className="flex flex-wrap gap-4 items-center">
        <Select value={timeRange} onValueChange={onTimeRangeChange}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="today">{t('attribution.today', 'Today')}</SelectItem>
            <SelectItem value="week">{t('attribution.thisWeek', 'This Week')}</SelectItem>
            <SelectItem value="month">{t('attribution.thisMonth', 'This Month')}</SelectItem>
            <SelectItem value="all">{t('attribution.allTime', 'All Time')}</SelectItem>
          </SelectContent>
        </Select>

        <Select value={exchange} onValueChange={onExchangeChange}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('attribution.allExchanges', 'All Exchanges')}</SelectItem>
            <SelectItem value="hyperliquid">
              <span className="flex items-center gap-2">
                <img src="/static/hyperliquid_logo.svg" alt="" className="w-4 h-4" />
                Hyperliquid
              </span>
            </SelectItem>
            <SelectItem value="binance">
              <span className="flex items-center gap-2">
                <img src="/static/binance_logo.svg" alt="" className="w-4 h-4" />
                Binance
              </span>
            </SelectItem>
          </SelectContent>
        </Select>

        <Select value={environment} onValueChange={onEnvironmentChange}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="testnet">测试网</SelectItem>
            <SelectItem value="mainnet">主网</SelectItem>
          </SelectContent>
        </Select>

        <Select value={accountId} onValueChange={onAccountIdChange}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t('attribution.allAccounts', 'All Accounts')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('attribution.allAccounts', 'All Accounts')}</SelectItem>
            {accounts.map(acc => (
              <SelectItem key={acc.id} value={String(acc.id)}>{acc.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        size="sm"
        className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white border-0 shadow-lg hover:shadow-xl transition-all"
        onClick={onOpenAiChat}
      >
        <Sparkles className="w-4 h-4 mr-2" />{t('attribution.aiAnalysisBtn', 'AI Attribution')}
      </Button>
    </div>
  )
}
