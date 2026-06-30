import { TradingAccount } from '@/lib/api'

export interface SignalConfig {
  name: string
  symbol: string
  description?: string
  exchange?: string  // Exchange: hyperliquid or binance
  _type?: 'signal' | 'pool'  // Type identifier from backend
  // For single signal
  trigger_condition?: {
    metric: string
    operator?: string
    threshold?: number
    time_window?: string
    direction?: string
    ratio_threshold?: number
    volume_threshold?: number
  }
  // For signal pool
  logic?: 'AND' | 'OR'
  signals?: Array<{
    metric?: string      // frontend field name
    indicator?: string   // AI output field name (same as metric)
    operator?: string
    threshold?: number
    time_window?: string
    // taker_volume composite signal fields
    direction?: string
    ratio_threshold?: number
    volume_threshold?: number
  }>
}

export interface AnalysisEntry {
  type: 'reasoning' | 'tool_call' | 'tool_result'
  round?: number
  content?: string
  name?: string
  arguments?: Record<string, unknown>
  result?: Record<string, unknown>
}

export interface ToolCallLogEntry {
  tool: string
  args: Record<string, unknown>
  result: string
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  signal_configs?: SignalConfig[] | null
  isStreaming?: boolean
  statusText?: string
  analysisLog?: AnalysisEntry[]
  toolCallsLog?: ToolCallLogEntry[]
  reasoningSnapshot?: string | null
  isInterrupted?: boolean
  interruptedRound?: number
}

export interface Conversation {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface CompressionPoint {
  message_id: number
  summary: string
  compressed_at: string
}

export interface TokenUsage {
  current_tokens: number
  max_tokens: number
  usage_ratio: number
  show_warning: boolean
}

export interface AiSignalChatModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreateSignal: (config: SignalConfig) => Promise<boolean>  // Returns true on success
  onCreatePool: (config: SignalConfig) => Promise<boolean>    // Create signal pool
  onPreviewSignal: (config: SignalConfig) => void
  accounts: TradingAccount[]
  accountsLoading: boolean
}

export type ChatTranslate = (key: string, fallback?: string) => string
