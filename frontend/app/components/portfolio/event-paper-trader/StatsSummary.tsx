import { useTranslation } from 'react-i18next'
import type { EventPaperTraderStats } from '@/lib/eventContractApi'
import { formatPnl } from './formatters'

interface StatsSummaryProps {
  stats: EventPaperTraderStats
}

function clampPct(value: number): number {
  return Math.min(Math.max(value, 0), 100)
}

/** CI range bar with a breakeven marker, mirroring the credibility-card idea
 * (backtest/CredibilityCard.tsx) but drawn as a range instead of a badge. */
function CiBar({ ciLow, ciHigh, breakeven }: { ciLow: number; ciHigh: number; breakeven: number }) {
  const low = clampPct(ciLow)
  const high = clampPct(ciHigh)
  const be = clampPct(breakeven)
  const beatsBreakeven = low > be

  return (
    <div className="relative mt-1.5 h-2 w-full rounded-full bg-primary/10">
      <div
        className={`absolute h-2 rounded-full ${beatsBreakeven ? 'bg-green-500' : 'bg-yellow-500'}`}
        style={{ left: `${low}%`, width: `${Math.max(high - low, 1)}%` }}
      />
      <div
        className="absolute -top-0.5 h-3 w-0.5 bg-foreground/70"
        style={{ left: `${be}%` }}
        title={`${breakeven.toFixed(2)}%`}
      />
    </div>
  )
}

export default function StatsSummary({ stats }: StatsSummaryProps) {
  const { t } = useTranslation()
  const decided = stats.decided
  const pnlPositive = stats.total_pnl >= 0

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <div>
        <div className="text-xs text-muted-foreground">
          {t('eventPaperTrader.decidedWinRate', 'Decided Win Rate')}
        </div>
        {decided > 0 ? (
          <>
            <div className="text-lg font-semibold">{stats.decided_win_rate.toFixed(1)}%</div>
            <div className="text-[11px] text-muted-foreground">
              {t('eventPaperTrader.ci', '95% CI')}: {stats.win_rate_ci_low.toFixed(1)}%–{stats.win_rate_ci_high.toFixed(1)}%
            </div>
            <CiBar ciLow={stats.win_rate_ci_low} ciHigh={stats.win_rate_ci_high} breakeven={stats.break_even_win_rate} />
            <div className="mt-1 text-[11px] text-muted-foreground">
              {t('eventPaperTrader.breakeven', 'Breakeven {{value}}%', { value: stats.break_even_win_rate.toFixed(2) })}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{t('eventPaperTrader.noDecided', 'No decided outcomes yet')}</p>
        )}
      </div>
      <div>
        <div className="text-xs text-muted-foreground">{t('eventPaperTrader.totalPnl', 'Total PnL')}</div>
        <div className={`text-lg font-semibold ${pnlPositive ? 'text-green-500' : 'text-red-500'}`}>
          {formatPnl(stats.total_pnl)}
        </div>
      </div>
      <div>
        <div className="text-xs text-muted-foreground">{t('eventPaperTrader.balance', 'Balance')}</div>
        <div className="text-lg font-semibold">{stats.current_balance.toFixed(2)}</div>
      </div>
      <div>
        <div className="text-xs text-muted-foreground">{t('eventPaperTrader.openBets', 'Open Bets')}</div>
        <div className="text-lg font-semibold">{stats.open_bets}</div>
      </div>
    </div>
  )
}
