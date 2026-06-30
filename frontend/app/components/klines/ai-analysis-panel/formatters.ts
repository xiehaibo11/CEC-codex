import type { PositionItem } from './types'

export const KLINE_LIMIT_OPTIONS = [50, 100, 200, 500]

export const FLOW_INDICATOR_LABELS: Record<string, string> = {
  cvd: 'CVD',
  taker_volume: 'Taker Vol',
  oi: 'OI',
  oi_delta: 'OI Delta',
  funding: 'Funding',
  depth_ratio: 'Depth',
  order_imbalance: 'Imbalance',
}

export function computeMA(data: any[], period: number) {
  if (!data || data.length < period) return []
  const closes = data.map((k) => Number(k.close || k.c))
  const ma: number[] = []
  for (let i = period - 1; i < closes.length; i++) {
    const slice = closes.slice(i - period + 1, i + 1)
    const avg = slice.reduce((a, b) => a + b, 0) / period
    ma.push(Number.isFinite(avg) ? Number(avg.toFixed(4)) : 0)
  }
  return Array(period - 1).fill(null).concat(ma)
}

export function mapExchangePosition(position: any, fallbackSymbol: string): PositionItem {
  return {
    symbol: position.coin || position.symbol || fallbackSymbol,
    size: position.sizeAbs ?? Math.abs(position.szi ?? 0),
    entry_price: position.entryPx ?? position.entry_price ?? null,
    mark_price: position.positionValue && position.sizeAbs ? position.positionValue / position.sizeAbs : null,
    position_value: position.positionValue ?? position.position_value ?? null,
    liquidation_price: position.liquidationPx ?? position.liquidation_price ?? null,
    side: position.side || '',
    leverage: position.leverage ?? null,
    unrealized_pnl: position.unrealizedPnl ?? position.unrealized_pnl ?? null,
    pnl_percentage: position.pnlPercent ?? position.pnl_percentage ?? null,
  }
}

export function createPositionPayload(positions: PositionItem[]) {
  return positions.map((position) => ({
    symbol: position.symbol,
    size: position.size,
    entry_price: position.entry_price,
    mark_price: position.mark_price,
    position_value: position.position_value,
    liquidation_price: position.liquidation_price,
    side: position.side,
    leverage: position.leverage,
    unrealized_pnl: position.unrealized_pnl,
    pnl_percentage: position.pnl_percentage,
  }))
}

export function createMarketDataPayload(marketData: any) {
  return {
    price: marketData?.price || 0,
    oracle_price: marketData?.oracle_price || 0,
    change24h: marketData?.change24h || 0,
    volume24h: marketData?.volume24h || 0,
    percentage24h: marketData?.percentage24h || 0,
    open_interest: marketData?.open_interest || 0,
    funding_rate: marketData?.funding_rate || 0,
  }
}

export function getAnalysisSummary(analysis: string) {
  if (!analysis) return ''

  const lines = analysis.split('\n')
  const summaryLines: string[] = []
  let foundFirstSection = false

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (foundFirstSection) break
      foundFirstSection = true
      summaryLines.push(line)
    } else if (foundFirstSection && line.trim()) {
      summaryLines.push(line)
      if (summaryLines.length >= 5) break
    }
  }

  return summaryLines.join('\n') || analysis.substring(0, 200) + '...'
}
