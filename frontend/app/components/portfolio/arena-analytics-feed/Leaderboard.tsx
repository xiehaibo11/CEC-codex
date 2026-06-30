import { ArenaAnalyticsAccount } from '@/lib/api'
import { getModelLogo } from '../logoAssets'
import {
  formatCurrency,
  formatDecimal,
  formatPercent,
  formatSignedCurrency,
  getTrendColor,
} from './formatters'

interface LeaderboardProps {
  accounts: ArenaAnalyticsAccount[]
  loading: boolean
}

export default function Leaderboard({ accounts, loading }: LeaderboardProps) {
  if (loading && accounts.length === 0) {
    return <div className="text-xs text-muted-foreground">Loading leaderboard…</div>
  }
  if (!loading && accounts.length === 0) {
    return <div className="text-xs text-muted-foreground">No analytics available yet.</div>
  }

  return (
    <>
      {accounts.map((account, index) => {
        const rank = index + 1
        const modelLogo = getModelLogo(account.account_name || account.model)
        const pnlClass = getTrendColor(account.total_pnl)
        const returnClass = getTrendColor(account.total_return_pct)
        const sharpeClass = getTrendColor(account.sharpe_ratio)
        const winRateClass = getTrendColor(account.win_rate)

        return (
          <div
            key={account.account_id}
            className="border border-border bg-muted/40 rounded-lg px-4 py-3 space-y-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-secondary flex items-center justify-center text-sm font-semibold text-secondary-foreground">
                  #{rank}
                </div>
                <div className="flex items-center gap-3">
                  {modelLogo && (
                    <img
                      src={modelLogo.src}
                      alt={modelLogo.alt}
                      className="h-10 w-10 rounded-full object-contain bg-background"
                      loading="lazy"
                    />
                  )}
                  <div>
                    <div className="text-sm font-semibold uppercase tracking-wide text-foreground">
                      {account.account_name}
                    </div>
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      {account.model || 'MODEL UNKNOWN'}
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-wide">
                <div>
                  <span className="block text-[10px] text-muted-foreground">总盈亏</span>
                  <span className={`font-semibold ${pnlClass}`}>{formatSignedCurrency(account.total_pnl)}</span>
                  <span className={`block text-[10px] ${returnClass}`}>{formatPercent(account.total_return_pct)}</span>
                </div>
                <div>
                  <span className="block text-[10px] text-muted-foreground">总资产</span>
                  <span className="font-semibold text-foreground">${formatCurrency(account.total_assets)}</span>
                </div>
                <div>
                  <span className="block text-[10px] text-muted-foreground">已付手续费</span>
                  <span className="font-semibold text-foreground">${formatCurrency(account.total_fees)}</span>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-muted-foreground">
              <div>
                <span className="block text-[10px] uppercase tracking-wide">最大盈利</span>
                <span className="font-semibold text-foreground">{formatSignedCurrency(account.biggest_gain)}</span>
              </div>
              <div>
                <span className="block text-[10px] uppercase tracking-wide">最大亏损</span>
                <span className="font-semibold text-foreground">{formatSignedCurrency(account.biggest_loss)}</span>
              </div>
              <div>
                <span className="block text-[10px] uppercase tracking-wide">夏普</span>
                <span className={`font-semibold ${sharpeClass}`}>{formatDecimal(account.sharpe_ratio, 3)}</span>
              </div>
              <div>
                <span className="block text-[10px] uppercase tracking-wide">胜率</span>
                <span className={`font-semibold ${winRateClass}`}>{formatPercent(account.win_rate, 1)}</span>
              </div>
            </div>
          </div>
        )
      })}
    </>
  )
}
