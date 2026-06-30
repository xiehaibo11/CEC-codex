import { useEffect, useState } from 'react'
import type { MonitorPosition } from './types'

export function PositionTicker({ positions }: { positions: MonitorPosition[] }) {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    if (positions.length <= 1) return
    const t = setInterval(() => setIdx(i => (i + 1) % positions.length), 2000)
    return () => clearInterval(t)
  }, [positions.length])
  if (positions.length === 0) return null
  const p = positions[idx % positions.length]
  const sideColor = p.side === 'LONG' ? '#4ade80' : '#f87171'
  const pnlColor = p.unrealizedPnl >= 0 ? '#4ade80' : '#f87171'
  return (
    <div className="flex items-center gap-1 font-mono" style={{ fontSize: 8, lineHeight: 1 }}>
      <span style={{ color: 'rgba(255,255,255,0.6)' }}>{p.symbol.replace('-USD', '').replace('USDT', '')}</span>
      <span style={{ color: sideColor, fontWeight: 'bold' }}>{p.side === 'LONG' ? 'L' : 'S'}</span>
      <span style={{ color: pnlColor }}>
        {p.unrealizedPnl >= 0 ? '+' : ''}{p.unrealizedPnl.toFixed(1)}
      </span>
    </div>
  )
}
