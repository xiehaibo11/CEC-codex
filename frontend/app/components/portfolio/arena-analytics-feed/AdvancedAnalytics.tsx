import { ArenaAnalyticsAccount } from '@/lib/api'
import { getModelLogo } from '../logoAssets'
import { formatCurrency, formatDate, formatMinutes, formatPercent, formatSignedCurrency, getTrendColor } from './formatters'

interface AdvancedAnalyticsProps {
  accounts: ArenaAnalyticsAccount[]
  loading: boolean
}

export default function AdvancedAnalytics({ accounts, loading }: AdvancedAnalyticsProps) {
  if (loading && accounts.length === 0) {
    return <div className="text-xs text-muted-foreground">Loading advanced analytics…</div>
  }
  if (!loading && accounts.length === 0) {
    return <div className="text-xs text-muted-foreground">No advanced analytics available.</div>
  }

  return (
    <>
      {accounts.map((account) => {
        const modelLogo = getModelLogo(account.account_name || account.model)
        const executionClass = getTrendColor(account.decision_execution_rate)

        return (
          <div key={`advanced-${account.account_id}`} className="border border-border rounded-lg bg-muted/30 p-4 space-y-4">
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
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-muted-foreground uppercase tracking-wide">
              <div className="border border-border rounded-md bg-background/40 p-3 space-y-1">
                <span className="text-[10px]">Decision Cadence</span>
                <div className="text-sm font-semibold text-foreground">
                  {formatMinutes(account.avg_decision_interval_minutes)}
                </div>
                <div className="text-[10px] text-muted-foreground/80">
                  First trade: {formatDate(account.first_trade_time)}
                </div>
                <div className="text-[10px] text-muted-foreground/80">
                  Last trade: {formatDate(account.last_trade_time)}
                </div>
              </div>
              <div className="border border-border rounded-md bg-background/40 p-3 space-y-1">
                <span className="text-[10px]">AI Execution</span>
                <div className="text-sm font-semibold text-foreground">
                  Decisions: {account.decision_count.toLocaleString()}
                </div>
                <div className={`text-[10px] font-semibold ${executionClass}`}>
                  Executed: {account.executed_decisions.toLocaleString()} ({formatPercent(account.decision_execution_rate, 1)})
                </div>
                <div className="text-[10px] text-muted-foreground/80">
                  Avg Target: {formatPercent(account.avg_target_portion, 1)}
                </div>
              </div>
              <div className="border border-border rounded-md bg-background/40 p-3 space-y-1">
                <span className="text-[10px]">Risk Snapshot</span>
                <div className="text-sm font-semibold text-foreground">
                  Balance σ: ${formatCurrency(account.balance_volatility)}
                </div>
                <div className="text-[10px] text-muted-foreground/80">
                  Biggest Win: {formatSignedCurrency(account.biggest_gain)}
                </div>
                <div className="text-[10px] text-muted-foreground/80">
                  Biggest Loss: {formatSignedCurrency(account.biggest_loss)}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </>
  )
}
