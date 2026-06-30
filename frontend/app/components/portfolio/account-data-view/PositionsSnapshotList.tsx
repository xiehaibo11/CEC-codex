import type { MutableRefObject } from 'react'
import FlipNumber from '../FlipNumber'
import RealtimePrice from '../RealtimePrice'
import type { PositionSummary } from './types'

interface PositionsSnapshotListProps {
  positions: PositionSummary[]
  wsRef?: MutableRefObject<WebSocket | null>
}

export default function PositionsSnapshotList({ positions, wsRef }: PositionsSnapshotListProps) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-3 overflow-x-auto pb-1">
        {positions.map((position) => (
          <div
            key={position.symbol}
            className="flex items-center gap-3 rounded-md bg-muted/70 px-3 py-2 shadow-sm border border-border/70 w-[160px]"
          >
            <span className="inline-flex h-6 w-6 items-center justify-center rounded bg-muted text-[11px] font-semibold text-muted-foreground">
              {position.symbol.slice(0, 4).toUpperCase()}
            </span>
            <div className="flex flex-col leading-tight">
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                {position.symbol}
              </span>
              <FlipNumber
                value={position.marketValue}
                prefix="$"
                decimals={2}
                className="text-sm font-semibold text-primary"
              />
              <RealtimePrice
                symbol={position.symbol}
                wsRef={wsRef}
                className="mt-0.5"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
