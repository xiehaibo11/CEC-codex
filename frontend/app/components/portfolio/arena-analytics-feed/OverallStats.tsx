import { ArenaAnalyticsSummary } from '@/lib/api'
import { formatCurrency, formatDecimal, formatPercent, formatSignedCurrency, getTrendColor } from './formatters'

interface OverallStatsProps {
  summary: ArenaAnalyticsSummary | null
  loading: boolean
  modelsTracked: number
  aggregates: {
    tradeCount: number
    decisionCount: number
    executedDecisions: number
  }
}

export default function OverallStats({ summary, loading, modelsTracked, aggregates }: OverallStatsProps) {
  if (loading && !summary) {
    return <div className="text-xs text-muted-foreground">加载整体统计...</div>
  }
  if (!summary) {
    return <div className="text-xs text-muted-foreground">暂无汇总数据</div>
  }

  const ratioClass = getTrendColor(summary.total_return_pct)
  const sharpeClass = getTrendColor(summary.average_sharpe_ratio)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border border-border rounded-lg bg-muted/40 p-4">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">总资产</div>
          <div className="text-lg font-semibold text-foreground">${formatCurrency(summary.total_assets)}</div>
        </div>
        <div className="border border-border rounded-lg bg-muted/40 p-4">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">综合盈亏</div>
          <div className={`text-lg font-semibold ${getTrendColor(summary.total_pnl)}`}>
            {formatSignedCurrency(summary.total_pnl)}
          </div>
          <div className={`text-[11px] ${ratioClass}`}>{formatPercent(summary.total_return_pct)}</div>
        </div>
        <div className="border border-border rounded-lg bg-muted/40 p-4">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Total Fees</div>
          <div className="text-lg font-semibold text-foreground">${formatCurrency(summary.total_fees)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border border-border rounded-lg bg-muted/30 p-4">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Total Volume</div>
          <div className="text-lg font-semibold text-foreground">${formatCurrency(summary.total_volume)}</div>
        </div>
        <div className="border border-border rounded-lg bg-muted/30 p-4">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Average Sharpe</div>
          <div className={`text-lg font-semibold ${sharpeClass}`}>
            {formatDecimal(summary.average_sharpe_ratio, 3)}
          </div>
        </div>
        <div className="border border-border rounded-lg bg-muted/30 p-4">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Models Tracked</div>
          <div className="text-lg font-semibold text-foreground">{modelsTracked}</div>
        </div>
      </div>

      <div className="border border-border rounded-lg bg-muted/20 p-4 space-y-3">
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Activity Snapshot</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs uppercase tracking-wide text-muted-foreground">
          <div>
            <span className="block text-[10px]">Total Trades</span>
            <span className="text-sm font-semibold text-foreground">{aggregates.tradeCount.toLocaleString()}</span>
          </div>
          <div>
            <span className="block text-[10px]">AI Decisions</span>
            <span className="text-sm font-semibold text-foreground">{aggregates.decisionCount.toLocaleString()}</span>
          </div>
          <div>
            <span className="block text-[10px]">Executed Decisions</span>
            <span className="text-sm font-semibold text-foreground">{aggregates.executedDecisions.toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
