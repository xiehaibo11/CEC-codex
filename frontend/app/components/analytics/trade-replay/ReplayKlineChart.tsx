import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createChart, CandlestickSeries, createSeriesMarkers } from 'lightweight-charts'
import type { Time } from 'lightweight-charts'
import { formatChartTime } from '@/lib/dateTime'
import { fetchReplayKlineData } from './api'
import { formatPrice } from './formatters'
import type { KlineMarker } from './types'

interface ReplayKlineChartProps {
  tradeId: number
  period: string
}

export function ReplayKlineChart({ tradeId, period }: ReplayKlineChartProps) {
  const { t } = useTranslation()
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null)
  const markerMapRef = useRef<Map<number, KlineMarker>>(new Map())

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tooltip, setTooltip] = useState<{ visible: boolean; x: number; y: number; marker: KlineMarker | null }>({
    visible: false, x: 0, y: 0, marker: null
  })

  useEffect(() => {
    if (!tradeId) return

    const timeoutId = setTimeout(() => {
      if (!chartContainerRef.current) {
        setError('Chart container not ready')
        setLoading(false)
        return
      }
      loadChart()
    }, 100)

    async function loadChart() {
      setLoading(true)
      setError(null)

      try {
        const result = await fetchReplayKlineData(tradeId, period)

        if (!result.klines || result.klines.length === 0) {
          setError('No K-line data available for this time range')
          setLoading(false)
          return
        }

        // Build marker map for tooltip lookup (use formatChartTime for consistency)
        markerMapRef.current.clear()
        const periodMs: Record<string, number> = { '5m': 300, '15m': 900, '1h': 3600, '4h': 14400 }
        const bucketSize = periodMs[period] || 300

        for (const marker of result.markers || []) {
          if (marker.timestamp) {
            // Align to bucket, then convert to local time (same as kline data)
            const bucketTime = Math.floor(marker.timestamp / bucketSize) * bucketSize
            const localBucketTime = formatChartTime(bucketTime)
            markerMapRef.current.set(localBucketTime, marker)
          }
        }

        // Create chart
        if (chartRef.current) {
          chartRef.current.remove()
        }

        if (!chartContainerRef.current) return

        const chart = createChart(chartContainerRef.current, {
          layout: { background: { color: 'transparent' }, textColor: '#9ca3af' },
          grid: {
            vertLines: { color: 'rgba(156, 163, 175, 0.1)' },
            horzLines: { color: 'rgba(156, 163, 175, 0.1)' },
          },
          crosshair: { mode: 1 },
          rightPriceScale: { borderColor: 'rgba(156, 163, 175, 0.2)' },
          timeScale: { borderColor: 'rgba(156, 163, 175, 0.2)', timeVisible: true, secondsVisible: false },
        })
        chartRef.current = chart

        const candlestickSeries = chart.addSeries(CandlestickSeries, {
          upColor: '#22c55e', downColor: '#ef4444',
          borderUpColor: '#22c55e', borderDownColor: '#ef4444',
          wickUpColor: '#22c55e', wickDownColor: '#ef4444',
        })

        const chartData = result.klines.map((item) => ({
          time: formatChartTime(item.timestamp) as Time,
          open: item.open, high: item.high, low: item.low, close: item.close,
        }))
        candlestickSeries.setData(chartData)

        // Add markers (use formatChartTime for consistency with kline data)
        const chartMarkers: { time: Time; position: 'aboveBar' | 'belowBar'; color: string; shape: 'arrowUp' | 'arrowDown' | 'circle'; text: string; size: number }[] = []
        for (const marker of result.markers || []) {
          if (marker.timestamp) {
            const bucketTime = Math.floor(marker.timestamp / bucketSize) * bucketSize
            const localBucketTime = formatChartTime(bucketTime)
            // Build marker text with price
            let markerText = ''
            let markerColor = '#9ca3af'
            let markerShape: 'arrowUp' | 'arrowDown' | 'circle' = 'circle'
            let markerPosition: 'aboveBar' | 'belowBar' = 'aboveBar'
            let markerSize = 2

            if (marker.type === 'entry') {
              const opText = marker.operation === 'buy' ? 'BUY' : 'SELL'
              const priceText = marker.entry_price ? `@${formatPrice(marker.entry_price)}` : ''
              markerText = `${opText}${priceText}`
              markerColor = marker.operation === 'buy' ? '#22c55e' : '#ef4444'
              markerShape = marker.operation === 'buy' ? 'arrowUp' : 'arrowDown'
              markerPosition = marker.operation === 'buy' ? 'belowBar' : 'aboveBar'
            } else if (marker.type === 'exit') {
              const priceText = marker.exit_price ? `@${formatPrice(marker.exit_price)}` : ''
              markerText = `CLOSE${priceText}`
              markerColor = '#3b82f6'
              markerShape = 'arrowDown'
              markerPosition = 'aboveBar'
            } else if (marker.type === 'hold') {
              // HOLD markers: small gray circle, no text to avoid clutter
              markerText = ''
              markerColor = '#9ca3af'
              markerShape = 'circle'
              markerPosition = 'aboveBar'
              markerSize = 1
            }

            chartMarkers.push({
              time: localBucketTime as Time,
              position: markerPosition,
              color: markerColor,
              shape: markerShape,
              text: markerText,
              size: markerSize,
            })
          }
        }
        if (chartMarkers.length > 0) {
          createSeriesMarkers(candlestickSeries, chartMarkers)
        }

        // Subscribe to crosshair for tooltip
        chart.subscribeCrosshairMove(param => {
          if (!param.time || !param.point) {
            setTooltip(prev => ({ ...prev, visible: false }))
            return
          }
          const chartTime = param.time as number
          const matchedMarker = markerMapRef.current.get(chartTime) || null
          if (matchedMarker) {
            setTooltip({ visible: true, x: param.point.x, y: param.point.y, marker: matchedMarker })
          } else {
            setTooltip(prev => ({ ...prev, visible: false }))
          }
        })

        chart.timeScale().fitContent()

        const handleResize = () => {
          if (chartContainerRef.current && chartRef.current) {
            chartRef.current.applyOptions({
              width: chartContainerRef.current.clientWidth,
              height: chartContainerRef.current.clientHeight,
            })
          }
        }
        window.addEventListener('resize', handleResize)
        handleResize()

        setLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load chart')
        setLoading(false)
      }
    }

    return () => {
      clearTimeout(timeoutId)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }
    }
  }, [tradeId, period])

  const renderTooltip = () => {
    if (!tooltip.marker) return null
    const m = tooltip.marker
    const isEntry = m.type === 'entry'
    const isHold = m.type === 'hold'

    // Get title based on type
    const getTitle = () => {
      if (isEntry) return t('attribution.replay.tooltipEntry', 'Entry Decision')
      if (isHold) return t('attribution.replay.tooltipHold', 'Hold Decision')
      return t('attribution.replay.tooltipExit', 'Exit Decision')
    }

    return (
      <div className="text-xs space-y-1">
        <div className="font-medium text-white border-b border-gray-600 pb-1 mb-1">
          {getTitle()}
        </div>
        <div><span className="text-gray-400">{t('attribution.replay.tooltipTime', 'Time')}:</span> <span className="text-white">{m.time ? new Date(m.time + 'Z').toLocaleString() : '-'}</span></div>
        <div><span className="text-gray-400">{t('attribution.replay.tooltipOp', 'Operation')}:</span> <span className={`font-medium ${m.operation === 'buy' ? 'text-green-400' : m.operation === 'sell' ? 'text-red-400' : m.operation === 'hold' ? 'text-gray-400' : 'text-blue-400'}`}>{m.operation.toUpperCase()}</span></div>
        {isEntry && m.entry_price && (
          <div><span className="text-gray-400">{t('attribution.replay.tooltipPrice', 'Price')}:</span> <span className="text-white">{formatPrice(m.entry_price)}</span></div>
        )}
        {isEntry && m.tp_price && (
          <div><span className="text-gray-400">TP:</span> <span className="text-green-400">{formatPrice(m.tp_price)}</span></div>
        )}
        {isEntry && m.sl_price && (
          <div><span className="text-gray-400">SL:</span> <span className="text-red-400">{formatPrice(m.sl_price)}</span></div>
        )}
        {isEntry && m.target_portion !== null && m.target_portion !== undefined && (
          <div><span className="text-gray-400">{t('attribution.replay.tooltipPortion', 'Target')}:</span> <span className="text-white">{(m.target_portion * 100).toFixed(0)}%</span></div>
        )}
        {m.type === 'exit' && m.exit_price && (
          <div><span className="text-gray-400">{t('attribution.replay.tooltipPrice', 'Price')}:</span> <span className="text-white">{formatPrice(m.exit_price)}</span></div>
        )}
        {m.type === 'exit' && m.exit_type && (
          <div><span className="text-gray-400">{t('attribution.replay.tooltipExitType', 'Exit Type')}:</span> <span className="text-white">{m.exit_type}</span></div>
        )}
        {m.type === 'exit' && m.realized_pnl !== null && m.realized_pnl !== undefined && (
          <div><span className="text-gray-400">{t('attribution.replay.tooltipPnl', 'PnL')}:</span> <span className={m.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>${m.realized_pnl.toFixed(2)}</span></div>
        )}
        {m.reason && (
          <div className="pt-1 border-t border-gray-600 mt-1">
            <div className="text-gray-400 mb-0.5">{t('attribution.replay.tooltipReason', 'Reason')}:</div>
            <div className="text-white text-[10px] leading-tight max-w-[200px] line-clamp-4">{m.reason}</div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="h-full w-full flex flex-col">
      {/* Chart container */}
      <div className="flex-1 relative [&_.tv-lightweight-charts]:!overflow-hidden [&_a[href*='tradingview']]:!hidden">
        <div ref={chartContainerRef} className="h-full w-full" />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-muted-foreground">Loading chart...</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-red-500">{error}</span>
          </div>
        )}
        {tooltip.visible && tooltip.marker && (
          <div
            className="absolute z-50 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-lg pointer-events-none"
            style={{
              left: Math.min(tooltip.x + 15, (chartContainerRef.current?.clientWidth || 400) - 220),
              top: Math.max(tooltip.y - 80, 10),
            }}
          >
            {renderTooltip()}
          </div>
        )}
      </div>
    </div>
  )
}
