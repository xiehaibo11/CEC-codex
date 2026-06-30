import { HistogramSeries, LineSeries } from 'lightweight-charts'
import type { CandlestickData, IChartApi, Time } from 'lightweight-charts'
import { formatChartTime } from '../../../lib/dateTime'
import type { KlineData, MacdData } from './types'

export function getBucketSize(timeWindow: string): number {
  const match = timeWindow.match(/^(\d+)([mhd])$/)
  if (!match) return 300
  const [, num, unit] = match
  const n = parseInt(num)
  if (unit === 'm') return n * 60
  if (unit === 'h') return n * 3600
  if (unit === 'd') return n * 86400
  return 300
}

export function getTriggerBucketTime(timestamp: number, bucketSize: number): number {
  const triggerSec = Math.floor(timestamp / 1000)
  const bucketSec = Math.floor(triggerSec / bucketSize) * bucketSize
  return formatChartTime(bucketSec)
}

export function toCandlestickData(klines: KlineData[]): CandlestickData<Time>[] {
  return klines.map(k => ({
    time: formatChartTime(k.timestamp / 1000) as Time,
    open: k.open,
    high: k.high,
    low: k.low,
    close: k.close,
  }))
}

export function addMacdOverlay(chart: IChartApi, klines: KlineData[], macd?: MacdData): void {
  if (!macd || !macd.macd || !macd.signal || !macd.histogram) return

  const prices = klines.flatMap(k => [k.high, k.low])
  const priceMin = Math.min(...prices)
  const priceMax = Math.max(...prices)
  const priceRange = priceMax - priceMin
  const macdDisplayMin = priceMin - priceRange * 0.05
  const macdDisplayMax = priceMin + priceRange * 0.20
  const allMacdValues = [...macd.macd, ...macd.signal, ...macd.histogram].filter(v => v !== 0)

  if (allMacdValues.length === 0) return

  const macdMin = Math.min(...allMacdValues)
  const macdMax = Math.max(...allMacdValues)
  const macdRange = macdMax - macdMin || 1
  const scaleToPrice = (value: number) => {
    const normalized = (value - macdMin) / macdRange
    return macdDisplayMin + normalized * (macdDisplayMax - macdDisplayMin)
  }

  const histogramSeries = chart.addSeries(HistogramSeries, {
    priceScaleId: 'right',
    priceFormat: { type: 'price' },
    base: scaleToPrice(0),
  })
  histogramSeries.setData(klines.map((k, i) => ({
    time: formatChartTime(k.timestamp / 1000) as Time,
    value: scaleToPrice(macd.histogram[i] || 0),
    color: (macd.histogram[i] || 0) >= 0 ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
  })))

  const macdLineSeries = chart.addSeries(LineSeries, {
    color: '#2962FF',
    lineWidth: 1,
    priceScaleId: 'right',
    priceFormat: { type: 'price' },
  })
  macdLineSeries.setData(klines.map((k, i) => ({
    time: formatChartTime(k.timestamp / 1000) as Time,
    value: scaleToPrice(macd.macd[i] || 0),
  })))

  const signalLineSeries = chart.addSeries(LineSeries, {
    color: '#FF6D00',
    lineWidth: 1,
    priceScaleId: 'right',
    priceFormat: { type: 'price' },
  })
  signalLineSeries.setData(klines.map((k, i) => ({
    time: formatChartTime(k.timestamp / 1000) as Time,
    value: scaleToPrice(macd.signal[i] || 0),
  })))
}
