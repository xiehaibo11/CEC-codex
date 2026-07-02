import { useCallback } from 'react'
import type { MouseEvent } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import FlipNumber from '../FlipNumber'
import { formatAccountName } from './assetCurveProcessing'
import type { AccountMeta, AccountSummary, ChartPoint } from './types'

interface AssetCurveChartProps {
  chartData: ChartPoint[]
  accountSummaries: AccountSummary[]
  uniqueUsers: string[]
  accountMeta: Map<string, AccountMeta>
  yAxisDomain: [number, number]
  activeLegendAccountId: number | null
  hoveredAccountId: number | null
  logoPulseMap: Map<number, number>
  loading: boolean
  onChartClick: () => void
  onHoverAccount: (accountId: number | null) => void
  onLegendClick: (accountId: number | 'all') => void
}

export function AssetCurveChart({
  chartData,
  accountSummaries,
  uniqueUsers,
  accountMeta,
  yAxisDomain,
  activeLegendAccountId,
  hoveredAccountId,
  logoPulseMap,
  loading,
  onChartClick,
  onHoverAccount,
  onLegendClick,
}: AssetCurveChartProps) {
  const renderTerminalDot = useCallback(
    (username: string, color: string) => {
      const meta = accountMeta.get(username)
      const accountId = meta?.accountId
      const logo = meta?.logo

      return (props: { cx?: number; cy?: number; index?: number; value?: number }) => {
        const { cx, cy, index, value } = props
        if (cx == null || cy == null || index == null || index !== chartData.length - 1) {
          return null
        }
        if (!meta || !logo) return null

        if (activeLegendAccountId && accountId !== activeLegendAccountId) {
          return null
        }

        const isHovered = hoveredAccountId === accountId
        const shouldHighlight = !hoveredAccountId || isHovered
        const pulseIteration = accountId != null ? logoPulseMap.get(accountId) ?? 0 : 0
        const size = 32
        const logoX = cx - size / 2
        const logoY = cy - size / 2
        const labelX = cx + size / 2 + 2
        const labelY = cy - 15

        const handleClick = (e: MouseEvent) => {
          e.stopPropagation()
          if (!meta.accountId) return
          onLegendClick(meta.accountId)
        }

        return (
          <g>
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
              style={{ overflow: 'visible', pointerEvents: 'auto' }}
            >
              <div
                style={{
                  width: size,
                  height: size,
                  borderRadius: '50%',
                  opacity: shouldHighlight ? 1 : 0.4,
                  cursor: meta.accountId ? 'pointer' : 'default',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: color,
                }}
                onClick={handleClick}
                onMouseEnter={() => meta.accountId && onHoverAccount(meta.accountId)}
                onMouseLeave={() => onHoverAccount(null)}
              >
                <img
                  src={logo.src}
                  alt={logo.alt}
                  style={{
                    width: size - 6,
                    height: size - 6,
                    borderRadius: '50%',
                    objectFit: 'contain',
                  }}
                />
              </div>
            </foreignObject>

            <foreignObject
              x={labelX}
              y={labelY}
              width={120}
              height={18}
              style={{ overflow: 'visible', pointerEvents: 'none' }}
            >
              <div
                className="px-3 py-1 text-xs font-bold transition-opacity duration-150 ease-out"
                style={{
                  backgroundColor: color,
                  color: '#fff',
                  boxShadow: '0 4px 8px rgba(0,0,0,0.12)',
                  opacity: shouldHighlight ? 1 : 0.45,
                  borderRadius: '12px',
                  display: 'inline-block',
                  whiteSpace: 'nowrap',
                }}
              >
                <FlipNumber
                  value={typeof value === 'number' ? value : 0}
                  prefix="$"
                  decimals={2}
                  className="text-white"
                />
              </div>
            </foreignObject>
          </g>
        )
      }
    },
    [
      accountMeta,
      activeLegendAccountId,
      chartData.length,
      hoveredAccountId,
      logoPulseMap,
      onHoverAccount,
      onLegendClick,
    ],
  )

  return (
    <div className="flex-1 relative min-h-[320px]">
      {loading ? (
        <div className="flex items-center justify-center h-full">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height="100%" style={{ outline: 'none' }}>
            <LineChart
              data={chartData}
              margin={{ top: 20, right: 160, left: 20, bottom: 40 }}
              onClick={onChartClick}
              onMouseLeave={() => onHoverAccount(null)}
              style={{ outline: 'none' }}
              tabIndex={-1}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" strokeWidth={0.5} />
              <XAxis
                dataKey="formattedTime"
                stroke="#333333"
                fontSize={12}
                interval={Math.ceil(chartData.length / 6)}
              />
              <YAxis
                stroke="#333333"
                fontSize={12}
                domain={yAxisDomain}
                tickFormatter={(value) => `$${Number(value).toLocaleString('en-US')}`}
                animationDuration={0}
                style={{ transition: 'all 0.6s cubic-bezier(0.4, 0.0, 0.2, 1)' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#ffffff',
                  border: '1px solid #e5e5e5',
                  borderRadius: '6px',
                  color: '#333333',
                  fontSize: '12px',
                }}
                formatter={(value: unknown, name: string) => [
                  `$${Number(value).toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`,
                  formatAccountName(name),
                ]}
                labelFormatter={(label: string) => label}
              />
              {uniqueUsers
                .filter((username) => {
                  if (!activeLegendAccountId) return true
                  const account = accountSummaries.find((acc) => acc.username === username)
                  return account?.accountId === activeLegendAccountId
                })
                .map((username) => {
                  const meta = accountMeta.get(username)
                  const color = meta?.color || '#666666'
                  const accountId = meta?.accountId
                  const isHovered = hoveredAccountId === accountId
                  const isHighlighted = !hoveredAccountId || isHovered

                  return (
                    <Line
                      key={username}
                      type="monotone"
                      dataKey={username}
                      stroke={color}
                      strokeWidth={isHighlighted ? 2.5 : 1}
                      dot={renderTerminalDot(username, color)}
                      activeDot={false}
                      connectNulls={false}
                      name={formatAccountName(username)}
                      strokeOpacity={isHighlighted ? 1 : 0.3}
                      isAnimationActive={false}
                      onMouseEnter={() => accountId && onHoverAccount(accountId)}
                      onMouseLeave={() => onHoverAccount(null)}
                      onClick={() => accountId && onLegendClick(accountId)}
                    />
                  )
                })}
            </LineChart>
          </ResponsiveContainer>

          <div className="absolute bottom-2 left-5 text-xs text-muted-foreground opacity-60">
            Data retained for 30 days
          </div>
        </>
      )}
    </div>
  )
}
