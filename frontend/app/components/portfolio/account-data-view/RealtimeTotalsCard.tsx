import FlipNumber from '../FlipNumber'
import type { AggregatedTotals } from './types'

interface RealtimeTotalsCardProps {
  totals: AggregatedTotals
}

const TOTAL_ITEMS = [
  { key: 'availableCash', label: '可用资金', className: 'text-foreground' },
  { key: 'frozenCash', label: '冻结资金', className: 'text-foreground' },
  { key: 'positionsValue', label: '持仓价值', className: 'text-foreground' },
  { key: 'totalAssets', label: '总资产', className: 'text-primary' },
] as const

export default function RealtimeTotalsCard({ totals }: RealtimeTotalsCardProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-wide text-muted-foreground">
      {TOTAL_ITEMS.map((item) => (
        <div key={item.key} className="flex flex-col leading-tight">
          <span>{item.label}</span>
          <FlipNumber
            value={totals[item.key]}
            prefix="$"
            decimals={2}
            className={`text-base font-semibold ${item.className}`}
          />
        </div>
      ))}
    </div>
  )
}
