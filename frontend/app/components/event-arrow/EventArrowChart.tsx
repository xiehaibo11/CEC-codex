import { useEffect, useRef } from 'react'
import { createChart, CandlestickSeries, createSeriesMarkers } from 'lightweight-charts'
import type {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  SeriesMarker,
  Time,
} from 'lightweight-charts'
import { formatChartTime } from '@/lib/dateTime'
import { parseUtcMs } from '@/components/analytics/event-paper-trader/formatters'
import type { EventPaperTraderBet } from '@/lib/eventContractApi'

/** 1-minute kline from `/api/market/kline-with-indicators`; timestamp is Unix seconds (UTC). */
export interface ArrowKline {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
}

interface EventArrowChartProps {
  klines: ArrowKline[]
  bets: EventPaperTraderBet[]
}

const WIN_COLOR = '#22c55e'
const LOSS_COLOR = '#ef4444'
const NEUTRAL_COLOR = '#9ca3af'

function markerColor(bet: EventPaperTraderBet): string {
  if (bet.result === 'win') return WIN_COLOR
  if (bet.result === 'loss') return LOSS_COLOR
  return NEUTRAL_COLOR // pending / draw stay neutral
}

/**
 * One permanent, close-confirmed arrow per bet, anchored to its entry-minute candle.
 * Long entries render an up arrow below the bar; short entries a down arrow above it.
 * Markers are recomputed only from immutable bet rows, so they never repaint away.
 */
function buildMarkers(
  bets: EventPaperTraderBet[],
  minTime: number,
  maxTime: number,
): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = []
  for (const bet of bets) {
    const entryMs = parseUtcMs(bet.entry_time ?? bet.decision_time)
    if (entryMs === null) continue
    const bucketSec = Math.floor(entryMs / 1000 / 60) * 60
    const time = formatChartTime(bucketSec)
    if (time < minTime || time > maxTime) continue
    if (bet.direction === 'long') {
      markers.push({
        time: time as Time,
        position: 'belowBar',
        shape: 'arrowUp',
        color: markerColor(bet),
        size: 1,
      })
    } else {
      markers.push({
        time: time as Time,
        position: 'aboveBar',
        shape: 'arrowDown',
        color: markerColor(bet),
        size: 1,
      })
    }
  }
  markers.sort((a, b) => (a.time as number) - (b.time as number))
  return markers
}

export default function EventArrowChart({ klines, bets }: EventArrowChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const scrolledRef = useRef(false)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Theme-neutral styling (transparent background + gray text/grid),
    // matching the approach used by klines/TradingViewChart.tsx.
    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 500,
      layout: {
        background: { color: 'transparent' },
        textColor: '#9ca3af',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(156, 163, 175, 0.1)' },
        horzLines: { color: 'rgba(156, 163, 175, 0.1)' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: 'rgba(156, 163, 175, 0.2)' },
      timeScale: {
        borderColor: 'rgba(156, 163, 175, 0.2)',
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 9,
        rightBarStaysOnScroll: false,
      },
    })

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    chartRef.current = chart
    seriesRef.current = series
    markersRef.current = createSeriesMarkers(series, [])

    const observer = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight || 500,
      })
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      markersRef.current = null
      seriesRef.current = null
      chartRef.current = null
      scrolledRef.current = false
      chart.remove()
    }
  }, [])

  useEffect(() => {
    const series = seriesRef.current
    if (!series) return
    series.setData(
      klines.map(k => ({
        time: formatChartTime(k.timestamp) as Time,
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
      })),
    )
    if (!scrolledRef.current && klines.length > 0) {
      chartRef.current?.timeScale().scrollToRealTime()
      scrolledRef.current = true
    }
  }, [klines])

  useEffect(() => {
    const markersApi = markersRef.current
    if (!markersApi) return
    if (klines.length === 0) {
      markersApi.setMarkers([])
      return
    }
    const times = klines.map(k => formatChartTime(k.timestamp))
    markersApi.setMarkers(buildMarkers(bets, Math.min(...times), Math.max(...times)))
  }, [bets, klines])

  return <div ref={containerRef} className="w-full h-full" />
}
