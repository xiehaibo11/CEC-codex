import type { WalletOption as SelectorWalletOption } from '../../hyperliquid/WalletSelector'

export interface AITrader {
  id: number
  name: string
  model: string
  is_active: boolean | string
}

export type WalletOption = SelectorWalletOption

export interface PositionItem {
  symbol?: string
  size?: number | null
  entry_price?: number | null
  mark_price?: number | null
  position_value?: number | null
  liquidation_price?: number | null
  side?: string
  leverage?: number | null
  unrealized_pnl?: number | null
  pnl_percentage?: number | null
}

export interface AIAnalysisPanelProps {
  symbol: string
  period: string
  klines: any[]
  indicators: Record<string, any>
  marketData: any
  selectedIndicators?: string[]
  selectedFlowIndicators?: string[]
  onAnalysisComplete?: () => void
  // 允许上层传入账户列表，暂无使用，预留扩展
  accounts?: AITrader[]
}

export interface AnalysisResult {
  success: boolean
  analysis_id?: number
  symbol?: string
  period?: string
  model?: string
  trader_name?: string
  analysis?: string
  created_at?: string
  prompt?: string
  error?: string
}
