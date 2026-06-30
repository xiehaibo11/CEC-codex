import type { MutableRefObject } from 'react'
import PositionsSnapshotList from './PositionsSnapshotList'
import RealtimeTotalsCard from './RealtimeTotalsCard'
import type { AggregatedTotals, PositionSummary } from './types'

interface SummaryCardsProps {
  positions: PositionSummary[]
  totals: AggregatedTotals
  wsRef?: MutableRefObject<WebSocket | null>
}

export default function SummaryCards({ positions, totals, wsRef }: SummaryCardsProps) {
  return (
    <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
      <PositionsSnapshotList positions={positions} wsRef={wsRef} />
      <RealtimeTotalsCard totals={totals} />
    </div>
  )
}
