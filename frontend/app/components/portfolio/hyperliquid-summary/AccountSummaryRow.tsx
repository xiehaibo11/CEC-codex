import { Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { getModelLogo } from '../logoAssets'
import PositionsSummary from './PositionsSummary'
import SummaryMetricCard from './SummaryMetricCard'
import { getApiUsageColor, getMarginStatus } from './status'
import type { AccountBalance, Position, SummaryTranslator } from './types'

interface AccountSummaryRowProps {
  account: AccountBalance
  positions: Position[]
  t: SummaryTranslator
  useScrollLayout: boolean
  onViewDetails: (account: AccountBalance) => void
}

export default function AccountSummaryRow({
  account,
  positions,
  t,
  useScrollLayout,
  onViewDetails,
}: AccountSummaryRowProps) {
  const logo = getModelLogo(account.accountName)
  const marginStatus = account.balance
    ? getMarginStatus(account.balance.marginUsagePercent, t)
    : null
  const isBinance = account.exchange === 'binance'
  const exchangeLogo = isBinance ? '/static/binance_logo.svg' : '/static/hyperliquid_logo.svg'

  return (
    <Card
      className={`p-4 space-y-3 hover:shadow-md transition-shadow ${useScrollLayout ? 'min-w-[400px] flex-shrink-0 snap-start' : ''}`}
    >
      <div className="flex items-center justify-between pb-2 border-b border-border">
        <div className="flex items-center gap-2">
          {logo && (
            <img
              src={logo.src}
              alt={logo.alt}
              className="h-6 w-6 rounded-full object-contain"
            />
          )}
          <span className="font-semibold text-sm truncate">
            {account.accountName}
          </span>
          <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-slate-800/80">
            <img
              src={exchangeLogo}
              alt={isBinance ? 'Binance' : 'Hyperliquid'}
              className="h-3.5 w-3.5"
            />
            <span className="text-[10px] font-medium text-slate-200">
              {isBinance ? 'Binance' : 'Hyperliquid'}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {account.balance && (
            <Button
              variant="outline"
              size="sm"
              className="text-[10px] h-6 px-2"
              onClick={() => onViewDetails(account)}
            >
              <Eye className="w-3 h-3 mr-1" />
              {t('common.details', 'Details')}
            </Button>
          )}
        </div>
      </div>

      {account.error && (
        <div className="text-xs text-red-600">{account.error}</div>
      )}

      {account.balance && (
        <div className="grid grid-cols-2 gap-3">
          <SummaryMetricCard label={t('account.equity', 'Equity')}>
            <div className="text-sm font-bold">
              ${account.balance.totalEquity.toLocaleString('en-US', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              })}
            </div>
          </SummaryMetricCard>

          <SummaryMetricCard label={t('account.margin', 'Margin')}>
            <div className={`text-sm font-medium ${marginStatus?.textColor || ''}`}>
              {account.balance.marginUsagePercent.toFixed(1)}%
            </div>
          </SummaryMetricCard>

          <SummaryMetricCard label={isBinance ? t('account.apiWeight', 'Weight/min') : 'API'}>
            {account.rateLimit ? (
              isBinance ? (
                <div className={`text-sm font-medium ${getApiUsageColor(account.rateLimit.usagePercent)}`}>
                  {account.rateLimit.nRequestsUsed}/{account.rateLimit.nRequestsCap}
                </div>
              ) : (
                <div className={`text-sm font-medium ${getApiUsageColor(account.rateLimit.usagePercent)}`}>
                  {(100 - account.rateLimit.usagePercent).toFixed(0)}%
                  <span className="text-[10px] text-muted-foreground ml-1">{t('account.left', 'left')}</span>
                </div>
              )
            ) : (
              <div className="text-sm text-muted-foreground">--</div>
            )}
          </SummaryMetricCard>

          <SummaryMetricCard label={t('account.winRate', 'Win Rate')}>
            {isBinance ? (
              <div className="text-sm text-muted-foreground">N/A</div>
            ) : account.tradingStats && account.tradingStats.total_trades > 0 ? (
              <div className="text-sm font-medium">
                {account.tradingStats.win_rate.toFixed(0)}%
                <span className="text-[10px] text-muted-foreground ml-1">
                  ({account.tradingStats.wins}W/{account.tradingStats.losses}L)
                </span>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">--</div>
            )}
          </SummaryMetricCard>
        </div>
      )}

      <PositionsSummary positions={positions} t={t} />
    </Card>
  )
}
