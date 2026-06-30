import type { TradingAccount } from '@/lib/api'

export interface DiagnosisResult {
  _type: 'diagnosis' | 'prompt_suggestion'
  title?: string
  severity?: string
  metrics?: Record<string, unknown>
  description?: string
  current_behavior?: string
  suggested_change?: string
  reason?: string
  roundIndex?: number  // Which conversation round this result belongs to
}

export interface AnalysisEntry {
  type: 'reasoning' | 'tool_call' | 'tool_result'
  content?: string
  name?: string
  arguments?: Record<string, unknown>
  result?: Record<string, unknown>
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  diagnosis_results?: DiagnosisResult[]
  isStreaming?: boolean
  statusText?: string
  analysisLog?: AnalysisEntry[]
  reasoning_snapshot?: string  // Stored reasoning from history
  tool_calls_log?: AnalysisEntry[]  // Stored tool calls log from history (renamed from analysis_log)
  is_complete?: boolean  // False if message was interrupted
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

export interface AiAttributionChatModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  accounts: TradingAccount[]
  accountsLoading: boolean
}
