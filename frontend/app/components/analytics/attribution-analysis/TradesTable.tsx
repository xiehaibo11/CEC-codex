import { useTranslation } from 'react-i18next'
import { Play } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { TradeDetail } from './types'

interface TradesTableProps {
  tagFilter: string | null
  onTagFilterChange: (value: string | null) => void
  trades: TradeDetail[]
  tradesLoading: boolean
  onReplayTrade: (tradeId: number) => void
}

export default function TradesTable({
  tagFilter,
  onTagFilterChange,
  trades,
  tradesLoading,
  onReplayTrade,
}: TradesTableProps) {
  const { t } = useTranslation()

  return (
    <>
      <div className="flex gap-2 mb-4 flex-wrap">
        <Button variant={tagFilter === null ? 'default' : 'outline'} size="sm" onClick={() => onTagFilterChange(null)}>
          {t('attribution.tags.all', 'All')}
        </Button>
        <Button variant={tagFilter === 'large_loss' ? 'default' : 'outline'} size="sm" onClick={() => onTagFilterChange('large_loss')}>
          {t('attribution.tags.largeLoss', 'Large Loss')}
        </Button>
        <Button variant={tagFilter === 'sl_triggered' ? 'default' : 'outline'} size="sm" onClick={() => onTagFilterChange('sl_triggered')}>
          {t('attribution.tags.slTriggered', 'SL Triggered')}
        </Button>
        <Button variant={tagFilter === 'consecutive_loss' ? 'default' : 'outline'} size="sm" onClick={() => onTagFilterChange('consecutive_loss')}>
          {t('attribution.tags.consecutiveLoss', 'Consecutive Loss')}
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {tradesLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : trades.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {t('attribution.noTrades', 'No trades found')}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left p-2 font-medium">币种</th>
                  <th className="text-left p-2 font-medium">Time</th>
                  <th className="text-center p-2 font-medium">Entry</th>
                  <th className="text-center p-2 font-medium">Exit</th>
                  <th className="text-right p-2 font-medium">总盈亏</th>
                  <th className="text-right p-2 font-medium">手续费</th>
                  <th className="text-right p-2 font-medium">净盈亏</th>
                  <th className="text-left p-2 font-medium">Tags</th>
                  <th className="text-center p-2 font-medium w-20"></th>
                </tr>
              </thead>
              <tbody>
                {trades.map(trade => (
                  <tr key={trade.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="p-2 font-medium">{trade.symbol}</td>
                    <td className="p-2 text-muted-foreground text-xs">
                      <div className="flex flex-col gap-0.5">
                        <span>
                          <span className="text-green-600 dark:text-green-400">In:</span>{' '}
                          {trade.entry_time ? new Date(trade.entry_time + 'Z').toLocaleString() : '-'}
                        </span>
                        <span>
                          <span className="text-red-600 dark:text-red-400">Out:</span>{' '}
                          {trade.exit_time ? new Date(trade.exit_time + 'Z').toLocaleString() : '-'}
                        </span>
                      </div>
                    </td>
                    <td className="p-2 text-center">
                      <span className={trade.entry_type === 'BUY' ? 'text-green-500' : trade.entry_type === 'SELL' ? 'text-red-500' : ''}>
                        {trade.entry_type}
                      </span>
                    </td>
                    <td className="p-2 text-center">
                      <span className={trade.exit_type === 'TP' ? 'text-green-500' : trade.exit_type === 'SL' ? 'text-red-500' : ''}>
                        {trade.exit_type}
                      </span>
                    </td>
                    <td className={`p-2 text-right ${trade.gross_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${trade.gross_pnl.toFixed(2)}
                    </td>
                    <td className="p-2 text-right text-orange-500">${trade.fees.toFixed(2)}</td>
                    <td className={`p-2 text-right ${trade.net_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${trade.net_pnl.toFixed(2)}
                    </td>
                    <td className="p-2">
                      <div className="flex gap-1 flex-wrap">
                        {trade.tags.map(tag => (
                          <Badge key={tag} variant="secondary" className={tagClassName(tag)}>
                            {tagLabel(tag, t)}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="p-2 text-center">
                      {trade.source === 'program' ? (
                        <span className="text-xs text-muted-foreground">Program</span>
                      ) : (
                        <Button variant="outline" size="sm" className="gap-1" onClick={() => onReplayTrade(trade.id)}>
                          <Play className="h-3 w-3" />
                          {t('attribution.replay.button', 'Replay')}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </>
  )
}

function tagClassName(tag: string) {
  if (tag === 'large_loss') return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
  if (tag === 'sl_triggered') return 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300'
  if (tag === 'consecutive_loss') return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
  return ''
}

function tagLabel(tag: string, t: ReturnType<typeof useTranslation>['t']) {
  if (tag === 'large_loss') return t('attribution.tags.largeLoss', 'Large Loss')
  if (tag === 'sl_triggered') return t('attribution.tags.slTriggered', 'SL Triggered')
  if (tag === 'consecutive_loss') return t('attribution.tags.consecutiveLoss', 'Consecutive Loss')
  return tag
}
