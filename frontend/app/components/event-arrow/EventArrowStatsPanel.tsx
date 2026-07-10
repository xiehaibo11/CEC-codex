import { useTranslation } from 'react-i18next'
import type { EventPaperTrader, EventPaperTraderDailyStats } from '@/lib/eventContractApi'

interface EventArrowStatsPanelProps {
  stats: EventPaperTraderDailyStats | null
  trader: EventPaperTrader
}

const EMPTY = '--'

function formatAmount(value: number): string {
  return Number(value ?? 0).toFixed(2)
}

function formatSigned(value: number): string {
  const v = Number(value ?? 0)
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}`
}

/**
 * Floating daily-stats card pinned to the top-right corner of the chart.
 * Backend resets the numbers at 00:00 in the requested timezone; when the
 * endpoint is unavailable every value degrades to "--".
 */
export default function EventArrowStatsPanel({ stats, trader }: EventArrowStatsPanelProps) {
  const { t } = useTranslation()

  const rows: Array<{ label: string; value: string; className?: string }> = [
    {
      label: t('eventArrow.openedToday'),
      value: stats ? String(stats.opened_today) : EMPTY,
    },
    {
      label: t('eventArrow.wins'),
      value: stats ? `${stats.wins} / ${formatAmount(stats.win_amount)}` : EMPTY,
      className: 'text-green-500',
    },
    {
      label: t('eventArrow.losses'),
      value: stats ? `${stats.losses} / ${formatAmount(stats.loss_amount)}` : EMPTY,
      className: 'text-red-500',
    },
    {
      label: t('eventArrow.winRate'),
      value: stats ? `${Number(stats.win_rate_pct ?? 0).toFixed(1)}%` : EMPTY,
    },
    {
      label: t('eventArrow.lossRate'),
      value: stats ? `${Number(stats.loss_rate_pct ?? 0).toFixed(1)}%` : EMPTY,
    },
    {
      label: t('eventArrow.netPnl'),
      value: stats ? formatSigned(stats.net_pnl) : EMPTY,
      className: stats && stats.net_pnl < 0 ? 'text-red-500' : 'text-green-500',
    },
  ]

  return (
    <div className="pointer-events-none absolute top-2 right-2 z-10 min-w-[180px] rounded-md border border-border bg-background/80 px-3 py-2 shadow-md backdrop-blur-sm">
      <div className="space-y-1 text-xs">
        {rows.map(row => (
          <div key={row.label} className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">{row.label}</span>
            <span className={`font-mono tabular-nums ${row.className ?? 'text-foreground'}`}>
              {row.value}
            </span>
          </div>
        ))}
      </div>
      {stats?.date && (
        <div className="mt-1 text-right text-[10px] text-muted-foreground">{stats.date}</div>
      )}
      <div className="mt-1 border-t border-border pt-1 text-[10px] text-muted-foreground">
        {trader.execution_mode === 'live' ? t('eventArrow.liveShort') : t('eventArrow.paperShort')} · 10x · 100 USDT · {stats?.opened_today ?? 0}/10
      </div>
      {trader.stop_reason && (
        <div className="mt-1 text-[10px] text-amber-600">
          {String(trader.stop_reason.reason ?? t('eventArrow.tradingStopped'))}
        </div>
      )}
    </div>
  )
}
