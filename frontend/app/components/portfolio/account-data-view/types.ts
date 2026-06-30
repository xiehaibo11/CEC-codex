import type { MutableRefObject } from 'react'
import type { AIDecision } from '@/lib/api'

export interface Account {
  id: number
  user_id: number
  name: string
  account_type: string
  initial_capital: number
  current_cash: number
  frozen_cash: number
}

export interface Overview {
  account: Account
  total_assets: number
  positions_value: number
}

export interface Position {
  id: number
  account_id?: number
  user_id?: number
  symbol: string
  name: string
  market: string
  quantity: number
  available_quantity: number
  avg_cost: number
  current_value?: number | null
  last_price?: number | null
  market_value?: number | null
}

export interface Order {
  id: number
  order_no: string
  symbol: string
  name: string
  market: string
  side: string
  order_type: string
  price?: number
  quantity: number
  filled_quantity: number
  status: string
}

export interface Trade {
  id: number
  order_id: number
  account_id?: number
  user_id?: number
  symbol: string
  name: string
  market: string
  side: string
  price: number
  quantity: number
  commission: number
  trade_time: string
}

export interface AccountDataViewProps {
  overview: Overview | null
  positions: Position[]
  orders: Order[]
  trades: Trade[]
  aiDecisions: AIDecision[]
  allAssetCurves: any[]
  wsRef?: MutableRefObject<WebSocket | null>
  onSwitchAccount: (accountId: number) => void
  onRefreshData: () => void
  accountRefreshTrigger?: number
  showAssetCurves?: boolean
  showStrategyPanel?: boolean
  accounts?: any[]
  loadingAccounts?: boolean
}

export type ArenaAccountSelection = number | 'all'

export interface PositionSummary {
  symbol: string
  marketValue: number
}

export interface AggregatedTotals {
  availableCash: number
  frozenCash: number
  positionsValue: number
  totalAssets: number
}
