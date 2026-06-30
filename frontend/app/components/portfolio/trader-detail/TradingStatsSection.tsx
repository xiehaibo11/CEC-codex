import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/dateTime'
import type { TradingStats } from '@/lib/hyperliquidApi'
import type { AccountDetailTranslator } from './types'

interface TradingStatsSectionProps {
  stats: TradingStats | null
  statsUpdated: number | null
  refreshing: boolean
  onRefresh: () => void
  t: AccountDetailTranslator
}

export default function TradingStatsSection({
  stats,
  statsUpdated,
  refreshing,
  onRefresh,
  t,
}: TradingStatsSectionProps) {
  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">{t('accountDetail.tradingStats', 'Trading Statistics')}</h3>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={refreshing}>
          <RefreshCw className={`w-3 h-3 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
          {t('common.refresh', 'Refresh')}
        </Button>
      </div>

      {stats && stats.total_trades > 0 ? (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3 text-sm">
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.winRate', 'Win Rate')}</div>
              <div className="font-bold text-lg">{stats.win_rate.toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.totalTrades', 'Total Trades')}</div>
              <div className="font-medium">{stats.total_trades}</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.winsLosses', 'Wins / Losses')}</div>
              <div className="font-medium">
                <span className="text-green-600">{stats.wins}W</span>
                {' / '}
                <span className="text-red-600">{stats.losses}L</span>
              </div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.profitFactor', 'Profit Factor')}</div>
              <div className={`font-bold ${stats.profit_factor >= 1 ? 'text-green-600' : 'text-red-600'}`}>
                {stats.profit_factor.toFixed(2)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3 text-sm pt-2 border-t">
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.totalPnl', 'Total PnL')}</div>
              <div className={`font-bold ${stats.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${stats.total_pnl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.avgWin', 'Avg Win')}</div>
              <div className="font-medium text-green-600">
                +${stats.avg_win.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.avgLoss', 'Avg Loss')}</div>
              <div className="font-medium text-red-600">
                ${stats.avg_loss.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">{t('accountDetail.grossProfit', 'Gross Profit')}</div>
              <div className="font-medium text-green-600">
                +${stats.gross_profit.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          {statsUpdated && (
            <div className="text-xs text-muted-foreground text-right">
              {t('accountDetail.lastUpdated', 'Last updated')}: {formatDateTime(new Date(statsUpdated))}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">
          {stats ? t('accountDetail.noClosedTrades', 'No closed trades yet') : t('accountDetail.clickRefreshStats', 'Click Refresh to load trading statistics')}
        </div>
      )}
    </div>
  )
}
