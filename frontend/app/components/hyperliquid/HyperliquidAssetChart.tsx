/**
 * HyperliquidAssetChart - Multi-Account Asset Curve Chart for Hyperliquid Mode
 *
 * Used by: HyperliquidView (line 6 import, line 56 usage)
 *
 * Features:
 * - 5-minute bucketed asset snapshots
 * - Multi-account display with individual curves
 * - Baseline reference line for profit/loss visualization
 * - Terminal dots with account logos and current values
 *
 * Data source: /api/account/asset-curve with environment parameter (testnet/mainnet)
 * Backend field: total_assets (NOT total_equity - field name fixed in v0.5.1)
 */
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  Line,
  Area,
  ComposedChart,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Customized,
  Brush
} from 'recharts'
import { Card } from '@/components/ui/card'
import { getModelColor } from '../portfolio/logoAssets'
import { formatDateTime } from '@/lib/dateTime'
import type {
  HyperliquidAssetChartProps,
  HyperliquidAssetData,
  HoveredTrade,
} from './hyperliquid-asset-chart/types'
import { processAssetData, computeTradeMarkers } from './hyperliquid-asset-chart/assetData'
import {
  renderTradeMarkers as renderTradeMarkersImpl,
  renderTerminalDot as renderTerminalDotImpl,
} from './hyperliquid-asset-chart/renderers'

export type { TradeMarker } from './hyperliquid-asset-chart/types'

export default function HyperliquidAssetChart({
  accountId,
  refreshTrigger,
  environment,
  selectedAccount,
  trades,
  selectedSymbol,
  selectedExchange,
}: HyperliquidAssetChartProps) {
  const [data, setData] = useState<HyperliquidAssetData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [logoPulseMap, setLogoPulseMap] = useState<Map<number, number>>(new Map())
  const [timeRange, setTimeRange] = useState<'7d' | '15d' | '1m' | '3m' | 'all'>('7d')
  const fetchingRef = useRef(false)

  // Hover tooltip state for trade markers
  const [hoveredTrade, setHoveredTrade] = useState<HoveredTrade | null>(null)

  // Brush state - preserve zoom level across data refreshes
  const [brushRange, setBrushRange] = useState<{ startIndex?: number; endIndex?: number }>({})
  const handleBrushChange = useCallback((range: { startIndex?: number; endIndex?: number }) => {
    setBrushRange(range)
  }, [])

  // Fetch Hyperliquid asset curve data (5-minute bucketed)
  const fetchData = useCallback(async () => {
    // Prevent duplicate requests
    if (fetchingRef.current) {
      return
    }
    fetchingRef.current = true
    try {
      setLoading(true)
      setError(null)

      const params = new URLSearchParams({
        timeframe: '5m',
        trading_mode: environment || 'testnet',
      })
      if (environment) {
        params.set('environment', environment)
      }
      if (selectedAccount && selectedAccount !== 'all') {
        params.set('account_id', String(selectedAccount))
      }

      // Calculate time range based on selected option
      const now = new Date()
      if (timeRange !== 'all') {
        const startDate = new Date(now)
        switch (timeRange) {
          case '7d':
            startDate.setDate(now.getDate() - 7)
            break
          case '15d':
            startDate.setDate(now.getDate() - 15)
            break
          case '1m':
            startDate.setMonth(now.getMonth() - 1)
            break
          case '3m':
            startDate.setMonth(now.getMonth() - 3)
            break
        }
        params.set('start_date', startDate.toISOString())
      }
      params.set('end_date', now.toISOString())

      const response = await fetch(`/api/account/asset-curve?${params.toString()}`)
      if (!response.ok) {
        throw new Error('Failed to fetch asset curve data')
      }

      const assetData = await response.json()
      setData(assetData || [])
    } catch (err) {
      console.error('Error fetching Hyperliquid asset curve:', err)
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
      fetchingRef.current = false
    }
  }, [environment, selectedAccount, timeRange])

  useEffect(() => {
    // Debounce: wait 300ms before fetching to avoid rapid successive calls
    const timeoutId = setTimeout(() => {
      fetchData()
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [fetchData, refreshTrigger])

  // Process chart data - group by account+exchange combination
  const { chartData, accountsData, yAxisDomain, baseline } = useMemo(
    () => processAssetData(data, selectedExchange),
    [data, selectedExchange]
  )

  // Process trade markers - snap to nearest 5-minute bucket
  const tradeMarkers = useMemo(
    () => computeTradeMarkers(trades, chartData, selectedAccount, selectedSymbol, selectedExchange),
    [trades, chartData, selectedAccount, selectedSymbol, selectedExchange]
  )

  // Render trade markers on chart
  const renderTradeMarkers = useCallback(
    (props: any) => renderTradeMarkersImpl(props, { tradeMarkers, chartData, accountsData, setHoveredTrade }),
    [tradeMarkers, chartData, accountsData]
  )

  // Terminal dot renderer with logo and value
  const renderTerminalDot = useCallback(
    (account: typeof accountsData[number]) =>
      (props: { cx?: number; cy?: number; index?: number; value?: number; payload?: any }) =>
        renderTerminalDotImpl(props, account, { chartData, logoPulseMap, brushRange }),
    [chartData, logoPulseMap, brushRange]
  )

  if (loading && data.length === 0) {
    return (
      <Card className="h-full flex items-center justify-center">
        <div className="text-muted-foreground">Loading Hyperliquid data...</div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="h-full flex items-center justify-center">
        <div className="text-destructive">{error}</div>
      </Card>
    )
  }

  if (chartData.length === 0) {
    return (
      <Card className="h-full flex items-center justify-center">
        <div className="text-muted-foreground">
          No Hyperliquid snapshot data yet.
        </div>
      </Card>
    )
  }

  return (
    <Card className="h-full">
      <div className="h-full relative">
        {/* Time Range Selector */}
        <div className="absolute top-3 right-3 z-10 flex gap-1 bg-white/90 backdrop-blur-sm rounded-lg p-1 shadow-sm border border-gray-200">
          {[
            { value: '7d' as const, label: '7D' },
            { value: '15d' as const, label: '15D' },
            { value: '1m' as const, label: '1M' },
            { value: '3m' as const, label: '3M' },
            { value: 'all' as const, label: 'ALL' },
          ].map((option) => (
            <button
              key={option.value}
              onClick={() => setTimeRange(option.value)}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                timeRange === option.value
                  ? 'bg-blue-500 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            margin={{ top: 20, right: 160, left: 20, bottom: 40 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="datetime_str"
              stroke="#888"
              fontSize={11}
              interval={Math.ceil(chartData.length / 6)}
              tickFormatter={(value) => {
                if (!value) return ''
                // Convert UTC datetime_str to local time
                // datetime_str format: "2025-11-22 05:51:00" (UTC, no timezone suffix)
                const isoString = value.replace(' ', 'T') + 'Z'  // Convert to ISO with UTC marker
                return formatDateTime(isoString, { style: 'short' })
              }}
            />
            <YAxis
              stroke="#888"
              fontSize={11}
              domain={yAxisDomain}
              tickFormatter={(value) => `$${Number(value).toLocaleString()}`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(255,255,255,0.95)',
                border: '1px solid #e0e0e0',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
              }}
              labelFormatter={(label) => {
                if (!label) return ''
                // Convert UTC datetime_str to local time
                const isoString = label.replace(' ', 'T') + 'Z'
                return formatDateTime(isoString, { style: 'medium' })
              }}
              formatter={(value: number, name: string) => [
                `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                name
              ]}
            />

            {baseline != null && accountsData.length === 1 && (
              <ReferenceLine y={baseline} stroke="#9CA3AF" strokeDasharray="4 4" />
            )}

            {baseline != null && accountsData.length === 1 && (
              <Area
                type="monotone"
                dataKey={accountsData[0].curveKey}
                stroke="none"
                fill="rgba(34,197,94,0.08)"
                baseValue={baseline}
                isAnimationActive={false}
              />
            )}

            {accountsData.map(account => {
              const color = account.logo?.color || getModelColor(account.username)
              return (
                <Line
                  key={account.key}
                  type="monotone"
                  dataKey={account.curveKey}
                  stroke={color}
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 6, fill: color }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              )
            })}

            {/* Terminal dots with logos */}
            {accountsData.map(account => (
              <Line
                key={`terminal-${account.key}`}
                type="monotone"
                dataKey={account.curveKey}
                stroke="transparent"
                strokeWidth={0}
                dot={renderTerminalDot(account)}
                activeDot={false}
                isAnimationActive={false}
              />
            ))}

            {/* Trade markers (B/S/C circles) */}
            {tradeMarkers.length > 0 && (
              <Customized component={renderTradeMarkers} />
            )}

            {/* Brush for zooming/panning */}
            <Brush
              dataKey="datetime_str"
              height={30}
              stroke="#8884d8"
              fill="#f5f5f5"
              onChange={handleBrushChange}
              startIndex={brushRange.startIndex !== undefined ? Math.min(brushRange.startIndex, chartData.length - 1) : undefined}
              endIndex={brushRange.endIndex !== undefined ? Math.min(brushRange.endIndex, chartData.length - 1) : undefined}
              tickFormatter={(value) => {
                if (!value) return ''
                const isoString = value.replace(' ', 'T') + 'Z'
                return formatDateTime(isoString, { style: 'short' })
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Trade marker tooltip */}
        {hoveredTrade && (
          <div
            className="absolute pointer-events-none bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs z-20"
            style={{
              left: hoveredTrade.x + 15,
              top: hoveredTrade.y - 40,
              transform: 'translateX(-50%)'
            }}
          >
            <div className="font-bold text-gray-800">
              {hoveredTrade.side} {hoveredTrade.symbol}
            </div>
            {hoveredTrade.price != null && (
              <div className="text-gray-600">
                ${hoveredTrade.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
