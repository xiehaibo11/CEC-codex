import { TradingAccount } from '@/lib/api'

export interface ToolCallEntry {
  type: 'tool_call' | 'tool_result' | 'reasoning'
  name?: string
  args?: Record<string, unknown>
  result?: string
  content?: string
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
  promptResult?: string | null
  isStreaming?: boolean
  isInterrupted?: boolean
  interruptedRound?: number
  statusText?: string
  toolCalls?: ToolCallEntry[]
  toolCallsLog?: ToolCallLogEntry[]
  reasoningSnapshot?: string | null
}

export interface Conversation {
  id: number
  title: string
  messageCount: number
  createdAt: string
  updatedAt: string
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

export interface ExtractedPrompt {
  id: number
  content: string
}

export interface AiPromptChatModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  accounts: TradingAccount[]
  accountsLoading: boolean
  onApplyPrompt: (promptText: string) => void
  promptId?: number | null
  promptName?: string | null
}
