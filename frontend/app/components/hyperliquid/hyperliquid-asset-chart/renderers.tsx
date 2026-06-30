import type { Dispatch, SetStateAction } from 'react'
import { getModelColor } from '../../portfolio/logoAssets'
import FlipNumber from '../../portfolio/FlipNumber'
import type { AccountInfo, HoveredTrade, TradeMarkerPoint } from './types'

// Trade marker colors matching Modelchat
export const getTradeMarkerStyle = (side: string) => {
  switch (side.toUpperCase()) {
    case 'BUY':
      return { bg: '#10B981', letter: 'B' } // emerald-500 (green)
    case 'SELL':
      return { bg: '#EF4444', letter: 'S' } // red-500 (red)
    case 'CLOSE':
      return { bg: '#3B82F6', letter: 'C' } // blue-500 (blue)
    case 'HOLD':
      return { bg: '#6B7280', letter: 'H' } // gray-500 (gray)
    default:
      return { bg: '#F97316', letter: '?' } // orange-500
  }
}

interface TradeMarkersContext {
  tradeMarkers: TradeMarkerPoint[]
  chartData: any[]
  accountsData: AccountInfo[]
  setHoveredTrade: Dispatch<SetStateAction<HoveredTrade | null>>
}

// Render trade markers on chart (used via recharts <Customized />)
export function renderTradeMarkers(props: any, ctx: TradeMarkersContext) {
  const { xAxisMap, yAxisMap } = props
  const { tradeMarkers, chartData, accountsData, setHoveredTrade } = ctx
  if (!xAxisMap || !yAxisMap || !tradeMarkers.length) return null

  const xAxis = Object.values(xAxisMap)[0] as any
  const yAxis = Object.values(yAxisMap)[0] as any
  if (!xAxis?.scale || !yAxis?.scale) return null

  return (
    <g className="trade-markers">
      {tradeMarkers.map((marker, idx) => {
        const dataPoint = chartData[marker.chartIndex]
        if (!dataPoint) return null

        const x = xAxis.scale(dataPoint.datetime_str)
        // Find the account this trade belongs to and get y value from that account's curve
        // Match by account_id and exchange (supports both Hyperliquid and Binance)
        const markerExchange = marker.exchange || 'hyperliquid'
        const account = accountsData.find(a => a.account_id === marker.account_id && a.exchange === markerExchange)
        if (!account) return null  // Skip if account not found (filtered out)
        const yValue = dataPoint[account.curveKey]
        if (yValue == null || x == null) return null

        const y = yAxis.scale(yValue)
        const { bg, letter } = getTradeMarkerStyle(marker.side)
        const size = 18

        return (
          <g
            key={`trade-${marker.trade_id}-${idx}`}
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setHoveredTrade({
              x,
              y,
              side: marker.side,
              symbol: marker.symbol,
              price: marker.price
            })}
            onMouseLeave={() => setHoveredTrade(null)}
          >
            <circle
              cx={x}
              cy={y}
              r={size / 2}
              fill={bg}
              stroke="#fff"
              strokeWidth={2}
              style={{ filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.2))' }}
            />
            <text
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#fff"
              fontSize={10}
              fontWeight="bold"
              style={{ pointerEvents: 'none' }}
            >
              {letter}
            </text>
          </g>
        )
      })}
    </g>
  )
}

interface TerminalDotContext {
  chartData: any[]
  logoPulseMap: Map<number, number>
  brushRange: { startIndex?: number; endIndex?: number }
}

// Terminal dot renderer with logo and value (one per account curve)
export function renderTerminalDot(
  props: { cx?: number; cy?: number; index?: number; value?: number; payload?: any },
  account: AccountInfo,
  ctx: TerminalDotContext,
) {
  const { cx, cy, index, payload } = props
  const { chartData, logoPulseMap, brushRange } = ctx
  if (cx == null || cy == null || index == null || !payload) return null
  if (chartData.length === 0) return null

  // Determine visible range from brush, or use full data range
  const visibleStart = brushRange.startIndex ?? 0
  const visibleEnd = brushRange.endIndex ?? chartData.length - 1

  // Find the last data point within visible range where this account has a value
  let lastVisibleIndex = -1
  for (let i = visibleEnd; i >= visibleStart; i--) {
    if (typeof chartData[i]?.[account.curveKey] === 'number') {
      lastVisibleIndex = i
      break
    }
  }

  if (lastVisibleIndex === -1 || index !== lastVisibleIndex) return null

  const value = payload[account.curveKey]
  if (typeof value !== 'number') return null

  const color = account.logo?.color || getModelColor(account.username)
  const pulseIteration = logoPulseMap.get(account.account_id) ?? 0
  const size = 32
  const logoX = cx - size / 2
  const logoY = cy - size / 2
  const labelX = cx + size / 2 + 2
  const labelY = cy - 18

  // Exchange badge position
  const badgeSize = 14
  const badgeX = cx + size / 2 - badgeSize / 2
  const badgeY = cy + size / 2 - badgeSize / 2

  return (
    <g key={`terminal-dot-${account.key}-${index}`}>
      {pulseIteration > 0 && (
        <circle
          cx={cx}
          cy={cy}
          r={size / 2}
          fill={color}
          className="pointer-events-none animate-ping-logo"
        />
      )}
      <foreignObject
        x={logoX}
        y={logoY}
        width={size}
        height={size}
        style={{ overflow: 'visible', pointerEvents: 'none' }}
      >
        <div
          style={{
            width: size,
            height: size,
            borderRadius: '50%',
            backgroundColor: color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 6px rgba(0,0,0,0.16)',
          }}
        >
          <img
            src={account.logo?.src}
            alt={account.logo?.alt}
            style={{
              width: size - 6,
              height: size - 6,
              borderRadius: '50%',
              objectFit: 'contain',
            }}
          />
        </div>
      </foreignObject>

      {/* Exchange badge (small icon at bottom-right of logo) */}
      <foreignObject
        x={badgeX}
        y={badgeY}
        width={badgeSize}
        height={badgeSize}
        style={{ overflow: 'visible', pointerEvents: 'none' }}
      >
        <div
          style={{
            width: badgeSize,
            height: badgeSize,
            borderRadius: '50%',
            backgroundColor: 'white',
            border: `2px solid ${account.exchange === 'binance' ? '#F0B90B' : '#00D395'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 2,
            boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          }}
        >
          <img
            src={`/static/${account.exchange}_logo.svg`}
            alt={account.exchange}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
            }}
          />
        </div>
      </foreignObject>

      <foreignObject
        x={labelX}
        y={labelY}
        width={120}
        height={24}
        style={{ overflow: 'visible', pointerEvents: 'none' }}
      >
        <div
          className="px-3 py-1 text-xs font-semibold text-white"
          style={{
            borderRadius: '12px',
            backgroundColor: color,
            display: 'inline-block',
            boxShadow: '0 4px 10px rgba(0,0,0,0.18)',
          }}
        >
          <FlipNumber value={value} prefix="$" decimals={2} className="text-white" />
        </div>
      </foreignObject>
    </g>
  )
}
