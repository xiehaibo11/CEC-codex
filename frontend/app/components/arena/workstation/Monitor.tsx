import { getScreenBg } from './helpers'
import { MonitorScreen } from './MonitorScreen'
import type { ExchangeMonitor } from './types'

export function Monitor({ ex, isOff, width, height }: {
  ex: ExchangeMonitor
  isOff: boolean
  width: number
  height: number
}) {
  const bg = isOff ? '#0a0a0a' : getScreenBg(ex.unrealizedPnl)
  const ledColor = isOff ? '#6b7280'
    : ex.unrealizedPnl && ex.unrealizedPnl > 0 ? '#22c55e'
    : ex.unrealizedPnl && ex.unrealizedPnl < 0 ? '#ef4444' : '#3b82f6'

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
    }}>
      <div style={{
        width, height,
        background: '#1a1c28', borderRadius: 5,
        border: '2px solid #2a2d3a', padding: 3, position: 'relative',
      }}>
        <div style={{
          width: '100%', height: '100%', background: bg,
          borderRadius: 3, overflow: 'hidden',
        }}>
          <MonitorScreen ex={ex} isOff={isOff} />
        </div>
        <div className="absolute top-1 left-2 rounded-full bg-white/5"
          style={{ width: 6, height: 2 }} />
        <div className="absolute" style={{
          bottom: 2, right: 4, width: 4, height: 4, borderRadius: '50%',
          background: ledColor, boxShadow: `0 0 4px ${ledColor}`,
        }} />
      </div>
      <div style={{ width: 8, height: 4, background: '#1a1d28' }} />
      <div style={{
        width: Math.min(width * 0.5, 30), height: 3,
        background: '#1a1d28', borderRadius: 2,
      }} />
    </div>
  )
}
