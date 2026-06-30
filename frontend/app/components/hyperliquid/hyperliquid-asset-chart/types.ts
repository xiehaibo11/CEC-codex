import type { HyperliquidEnvironment } from '@/lib/types/hyperliquid'

export interface HyperliquidAssetData {
  timestamp: number
  datetime_str: string
  account_id: number
  total_assets: number
  username: string
  wallet_address?: string | null
  exchange?: string  // 'hyperliquid' | 'binance'
}

export interface TradeMarker {
  trade_id: number
  trade_time: string
  side: string // 'BUY' | 'SELL' | 'CLOSE'
  symbol: string
  account_id: number
  price?: number
  exchange?: string // 'hyperliquid' | 'binance'
}

export interface HyperliquidAssetChartProps {
  accountId: number
  refreshTrigger?: number
  environment?: HyperliquidEnvironment
  selectedAccount?: number | 'all'
  trades?: TradeMarker[]
  selectedSymbol?: string | null
  selectedExchange?: 'all' | 'hyperliquid' | 'binance'
}

export interface AccountInfo {
  key: string  // "accountId_exchange"
  account_id: number
  username: string
  exchange: string
  curveKey: string  // unique key for chart dataKey
  logo: { src: string; alt: string; color?: string }
}

export interface ProcessedAssetData {
  chartData: any[]
  accountsData: AccountInfo[]
  yAxisDomain: number[]
  baseline: number | null
}

export interface TradeMarkerPoint {
  trade_id: number
  timestamp: number
  datetime_str: string
  side: string
  symbol: string
  price?: number
  chartIndex: number
  account_id: number
  exchange?: string
}

export interface HoveredTrade {
  x: number
  y: number
  side: string
  symbol: string
  price?: number
}
