export interface DecisionChainItem {
  id: number
  operation: string
  decision_time: string | null
  reason: string
  target_portion: number
  realized_pnl: number | null
}

export interface TradeReplayData {
  trade: {
    id: number
    symbol: string
    operation: string
    decision_time: string | null
    wallet_address: string
    hyperliquid_environment: string
    account_id: number
  }
  entry_decision: {
    id: number
    operation: string
    decision_time: string | null
    reason: string
  } | null
  exit_decision: {
    id: number
    operation: string
    decision_time: string | null
    reason: string
    exit_type: string
  } | null
  decisions_chain: DecisionChainItem[]
  summary: {
    entry_time: string | null
    exit_time: string | null
    hold_duration: string | null
    pnl: number
  }
  kline_params: {
    symbol: string
    start_time: string | null
    end_time: string | null
  } | null
}

export interface KlineMarker {
  type: 'entry' | 'exit' | 'hold'
  time: string | null
  timestamp: number | null
  operation: string
  reason: string
  target_portion?: number | null
  exit_type?: string
  realized_pnl?: number | null
  symbol: string
  entry_price?: number | null
  tp_price?: number | null
  sl_price?: number | null
  exit_price?: number | null
}

export interface ReplayKline {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
}

export interface ReplayKlineData {
  klines?: ReplayKline[]
  markers?: KlineMarker[]
}

export interface AnalysisEntry {
  type: 'reasoning' | 'tool_call' | 'tool_result'
  content?: string
  name?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  statusText?: string
  analysisLog?: AnalysisEntry[]
}

export interface ReplayAiChatProps {
  tradeData: TradeReplayData
  selectedAccountId: number | null
}

export interface TradeReplayModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  tradeId: number | null
}

export type DecisionGroup = {
  type: 'single' | 'hold_group'
  items: DecisionChainItem[]
}
