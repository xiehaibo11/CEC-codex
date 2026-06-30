import { getModelChartLogo, getModelColor } from '../../portfolio/logoAssets'
import { SMALL_GAP_FILL_THRESHOLD_SECONDS } from './constants'
import type {
  AccountInfo,
  HyperliquidAssetChartProps,
  HyperliquidAssetData,
  ProcessedAssetData,
  TradeMarker,
  TradeMarkerPoint,
} from './types'

/**
 * Process raw asset-curve snapshots into chart-ready series.
 * Groups by account+exchange combination, fills small snapshot gaps, and
 * computes a baseline + Y-axis domain. Pure function extracted verbatim from
 * the original component's useMemo.
 */
export function processAssetData(
  data: HyperliquidAssetData[],
  selectedExchange: HyperliquidAssetChartProps['selectedExchange'],
): ProcessedAssetData {
  if (!data.length) return { chartData: [], accountsData: [], yAxisDomain: [0, 1000], baseline: 1000 }

  // Filter data by selected exchange
  const filteredData = selectedExchange && selectedExchange !== 'all'
    ? data.filter(item => (item.exchange || 'hyperliquid') === selectedExchange)
    : data

  if (!filteredData.length) return { chartData: [], accountsData: [], yAxisDomain: [0, 1000], baseline: 1000 }

  // Group by timestamp and create chart points
  const timeGroups = new Map<number, any>()
  // Key: "accountId_exchange" to support same account on multiple exchanges
  const accounts = new Map<string, AccountInfo>()

  filteredData.forEach(item => {
    if (!timeGroups.has(item.timestamp)) {
      timeGroups.set(item.timestamp, {
        timestamp: item.timestamp,
        datetime_str: item.datetime_str
      })
    }

    const exchange = item.exchange || 'hyperliquid'
    // Create unique curve key: "username (Exchange Name)" for multi-exchange accounts
    const exchangeName = exchange === 'hyperliquid' ? 'Hyperliquid' : 'Binance'
    const curveKey = `${item.username} (${exchangeName})`
    const accountKey = `${item.account_id}_${exchange}`

    const point = timeGroups.get(item.timestamp)!
    point[curveKey] = item.total_assets

    if (!accounts.has(accountKey)) {
      const baseLogo = getModelChartLogo(item.username)
      // Adjust color for Binance to differentiate from Hyperliquid
      const color = exchange === 'binance'
        ? '#F0B90B'  // Binance yellow
        : baseLogo.color || getModelColor(item.username)

      accounts.set(accountKey, {
        key: accountKey,
        account_id: item.account_id,
        username: item.username,
        exchange,
        curveKey,
        logo: { ...baseLogo, color }
      })
    }
  })

  const rawChartData = Array.from(timeGroups.values()).sort((a, b) => a.timestamp - b.timestamp)
  const accountsData: AccountInfo[] = Array.from(accounts.entries()).map(([key, info]) => ({
    ...info,
    key,  // "accountId_exchange"
  }))

  // Smooth over short snapshot gaps caused by transient network hiccups.
  // Long gaps remain disconnected to avoid implying continuous data where none exists.
  const chartData = rawChartData.map(point => ({ ...point }))
  for (const account of accountsData) {
    let previousKnownIndex: number | null = null

    for (let i = 0; i < chartData.length; i++) {
      const value = chartData[i][account.curveKey]
      if (typeof value !== 'number') continue

      if (previousKnownIndex !== null) {
        const previousPoint = chartData[previousKnownIndex]
        const gapSeconds = chartData[i].timestamp - previousPoint.timestamp
        if (gapSeconds > 0 && gapSeconds <= SMALL_GAP_FILL_THRESHOLD_SECONDS) {
          for (let j = previousKnownIndex + 1; j < i; j++) {
            if (chartData[j][account.curveKey] == null) {
              chartData[j][account.curveKey] = previousPoint[account.curveKey]
            }
          }
        }
      }

      previousKnownIndex = i
    }
  }

  // Calculate baseline (initial capital) - only meaningful for single account view
  let baseline: number | null = null
  if (chartData.length > 0 && accountsData.length === 1) {
    // Single account: use first non-null data point as starting capital
    for (const point of chartData) {
      const val = point[accountsData[0].curveKey]
      if (typeof val === 'number') {
        baseline = val
        break
      }
    }
  }

  // Calculate Y-axis domain with smart padding
  const allValues = filteredData.map(item => item.total_assets).filter(val => typeof val === 'number')

  if (allValues.length === 0) return { chartData, accountsData, yAxisDomain: [0, 1000], baseline }

  const minValue = Math.min(...allValues)
  const maxValue = Math.max(...allValues)
  const range = maxValue - minValue

  const hasMultipleAccounts = accountsData.length > 1
  const paddingPercent = hasMultipleAccounts ? 0.05 : 0.15

  // When all values are the same (range = 0), use fixed padding based on baseline
  const padding = range > 0 ? range * paddingPercent : (baseline as number) * 0.1

  return {
    chartData,
    accountsData,
    yAxisDomain: [Math.max(0, minValue - padding), maxValue + padding],
    baseline
  }
}

/**
 * Snap trade markers to the nearest 5-minute chart bucket. Filters by the
 * currently selected account / symbol / exchange. Pure function extracted
 * verbatim from the original component's useMemo.
 */
export function computeTradeMarkers(
  trades: TradeMarker[] | undefined,
  chartData: any[],
  selectedAccount: HyperliquidAssetChartProps['selectedAccount'],
  selectedSymbol: HyperliquidAssetChartProps['selectedSymbol'],
  selectedExchange: HyperliquidAssetChartProps['selectedExchange'],
): TradeMarkerPoint[] {
  if (!trades?.length || !chartData.length) return []

  const timestamps = chartData.map(d => d.timestamp)
  const markers: TradeMarkerPoint[] = []

  trades.forEach(trade => {
    if (!trade.trade_time) return
    // Filter by selected account
    if (selectedAccount && selectedAccount !== 'all' && trade.account_id !== selectedAccount) return
    // Filter by selected symbol
    if (selectedSymbol && trade.symbol !== selectedSymbol) return
    // Filter by selected exchange
    const tradeExchange = trade.exchange || 'hyperliquid'
    if (selectedExchange && selectedExchange !== 'all' && tradeExchange !== selectedExchange) return

    // Convert trade_time ISO string to Unix timestamp
    const tradeTs = Math.floor(new Date(trade.trade_time + (trade.trade_time.includes('Z') ? '' : 'Z')).getTime() / 1000)

    // Find nearest 5-minute bucket
    let nearestIdx = 0
    let minDiff = Math.abs(timestamps[0] - tradeTs)
    for (let i = 1; i < timestamps.length; i++) {
      const diff = Math.abs(timestamps[i] - tradeTs)
      if (diff < minDiff) {
        minDiff = diff
        nearestIdx = i
      }
    }

    // Only include if within 5 minutes (300 seconds) of a data point
    if (minDiff <= 300) {
      markers.push({
        trade_id: trade.trade_id,
        timestamp: timestamps[nearestIdx],
        datetime_str: chartData[nearestIdx].datetime_str,
        side: trade.side,
        symbol: trade.symbol,
        price: trade.price,
        chartIndex: nearestIdx,
        account_id: trade.account_id,
        exchange: trade.exchange
      })
    }
  })

  return markers
}
