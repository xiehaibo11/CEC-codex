import { useEffect, useRef, useState } from 'react'
import { createChart, CandlestickSeries, IChartApi, ISeriesApi, createSeriesMarkers } from 'lightweight-charts'
import type { Time } from 'lightweight-charts'
import {
  addMacdOverlay,
  getBucketSize,
  getTriggerBucketTime,
  toCandlestickData,
} from './signal-preview-chart/chart-helpers'
import { SignalPreviewTooltip } from './signal-preview-chart/SignalPreviewTooltip'
import type { SignalPreviewChartProps, TooltipState, TriggerBucketContent } from './signal-preview-chart/types'

export default function SignalPreviewChart({ klines, triggers, timeWindow, signalMetric, macd }: SignalPreviewChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false, x: 0, y: 0, content: null
  })

  // Build time-to-trigger map for quick lookup (may have multiple triggers per bucket)
  const triggerMap = useRef<Map<number, TriggerBucketContent>>(new Map())

  useEffect(() => {
    // Build trigger map using floored bucket time as key (to match K-line time)
    triggerMap.current.clear()
    const bucketSize = getBucketSize(timeWindow)

    triggers.forEach(t => {
      const chartTime = getTriggerBucketTime(t.timestamp, bucketSize)

      // Store all triggers for this bucket (may have multiple)
      const existing = triggerMap.current.get(chartTime)
      if (existing) {
        // Merge triggered_signals if both have them
        if (Array.isArray(existing)) {
          existing.push(t)
        } else {
          triggerMap.current.set(chartTime, [existing, t])
        }
      } else {
        triggerMap.current.set(chartTime, t)
      }
    })
  }, [triggers, timeWindow])

  useEffect(() => {
    if (!chartContainerRef.current || klines.length === 0) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 500,
      layout: {
        background: { color: '#1a1a2e' },
        textColor: '#d1d5db',
      },
      grid: {
        vertLines: { color: '#2d2d44' },
        horzLines: { color: '#2d2d44' },
      },
      crosshair: {
        mode: 1,
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#2d2d44',
        barSpacing: 9,
        rightBarStaysOnScroll: false,
      },
      rightPriceScale: {
        borderColor: '#2d2d44',
      },
    })

    chartRef.current = chart

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    seriesRef.current = candlestickSeries

    candlestickSeries.setData(toCandlestickData(klines))
    addMacdOverlay(chart, klines, macd)

    // Add trigger markers - use same bucket time as triggerMap
    if (triggers.length > 0) {
      const bucketSize = getBucketSize(timeWindow)
      const markers = triggers.map(t => ({
        time: getTriggerBucketTime(t.timestamp, bucketSize) as Time,
        position: 'aboveBar' as const,
        color: '#F8CD74',
        shape: 'arrowDown' as const,
        text: '⚡',
        size: 2,
      }))
      createSeriesMarkers(candlestickSeries, markers)
    }

    // Subscribe to crosshair move for tooltip
    chart.subscribeCrosshairMove(param => {
      if (!param.time || !param.point) {
        setTooltip(prev => ({ ...prev, visible: false }))
        return
      }

      // param.time is the local chart time (same format as triggerMap keys)
      const chartTime = param.time as number

      // Direct lookup - triggerMap uses same time format as chart
      const matchedTrigger = triggerMap.current.get(chartTime) || null

      if (matchedTrigger) {
        setTooltip({
          visible: true,
          x: param.point.x,
          y: param.point.y,
          content: matchedTrigger,
        })
      } else {
        setTooltip(prev => ({ ...prev, visible: false }))
      }
    })

    chart.timeScale().scrollToRealTime()

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [klines, triggers, macd])

  return (
    <div className="relative w-full h-[500px]">
      <div ref={chartContainerRef} className="w-full h-full" />
      {macd && (
        <div className="absolute top-2 left-2 text-xs text-gray-400 bg-gray-900/70 px-2 py-1 rounded">
          MACD (12, 26, 9)
        </div>
      )}
      <SignalPreviewTooltip
        tooltip={tooltip}
        signalMetric={signalMetric}
        containerWidth={chartContainerRef.current?.clientWidth || 400}
      />
    </div>
  )
}
