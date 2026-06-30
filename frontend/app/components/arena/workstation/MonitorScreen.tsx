import { useEffect, useState } from 'react'
import { EXCHANGE_LABEL } from './helpers'
import { MiniEquityLine } from './MiniEquityLine'
import { PositionTicker } from './PositionTicker'
import type { ExchangeMonitor } from './types'

export function MonitorScreen({ ex, isOff }: {
  ex: ExchangeMonitor
  isOff: boolean
}) {
  const [cursorOn, setCursorOn] = useState(true)
  const label = EXCHANGE_LABEL[ex.exchange] || {
    short: ex.exchange.slice(0, 2).toUpperCase(), color: '#9ca3af',
  }

  useEffect(() => {
    if (isOff) return
    const t = setInterval(() => setCursorOn(v => !v), 600)
    return () => clearInterval(t)
  }, [isOff])

  const chartColor = ex.unrealizedPnl && ex.unrealizedPnl > 0
    ? '#16a34a' : ex.unrealizedPnl && ex.unrealizedPnl < 0
    ? '#dc2626' : '#3b82f6'

  return (
    <div className="flex flex-col w-full h-full p-1.5" style={{ gap: 1 }}>
      {/* Header: exchange label + equity */}
      <div className="flex items-center justify-between">
        <span className="font-mono font-bold" style={{
          fontSize: 10, color: label.color,
        }}>
          {label.short}
        </span>
        {isOff && (
          <span className="font-mono" style={{
            fontSize: 8, color: 'rgba(255,255,255,0.35)',
          }}>休眠</span>
        )}
        {!isOff && ex.equity !== null && (
          <span className="font-mono" style={{
            fontSize: 9, color: 'rgba(255,255,255,0.6)',
          }}>
            ${ex.equity.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
        )}
      </div>
      {/* PnL line */}
      {!isOff && (
        <div className="flex items-center justify-between">
          {ex.unrealizedPnl !== null && ex.unrealizedPnl !== 0 ? (
            <span className="font-mono font-bold" style={{
              fontSize: 10,
              color: ex.unrealizedPnl > 0 ? '#4ade80' : '#f87171',
            }}>
              {ex.unrealizedPnl > 0 ? '+' : ''}
              ${Math.abs(ex.unrealizedPnl).toFixed(1)}
            </span>
          ) : (
            <span className="font-mono" style={{
              fontSize: 9,
              color: cursorOn ? '#4ade80' : 'transparent',
            }}>_</span>
          )}
          {ex.positionCount > 0 && (
            <span className="font-mono" style={{ fontSize: 8, color: 'rgba(255,255,255,0.35)' }}>
              {ex.positionCount} pos
            </span>
          )}
        </div>
      )}
      {/* Position ticker */}
      {!isOff && ex.positions.length > 0 && (
        <PositionTicker positions={ex.positions} />
      )}
      {/* Mini equity chart */}
      {!isOff && (
        <div className="mt-auto" style={{ height: 20 }}>
          {ex.equityHistory.length >= 2 ? (
            <MiniEquityLine data={ex.equityHistory} color={chartColor} width={155} height={20} />
          ) : (
            <div className="flex items-end gap-px" style={{ height: 12 }}>
              {[3, 5, 4, 7, 5, 8, 6, 4, 7, 5, 6, 8].map((h, i) => (
                <div key={i} style={{
                  width: 2, height: h, borderRadius: 1, opacity: 0.3,
                  background: chartColor,
                }} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
