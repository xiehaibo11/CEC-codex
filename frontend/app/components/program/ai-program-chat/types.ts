export interface SaveSuggestion {
  code: string
  name: string
  description: string
}

export interface ToolCallEntry {
  type: 'tool_call' | 'tool_result' | 'reasoning'
  name?: string
  args?: Record<string, unknown>
  result?: string
  content?: string
}

// API format for tool_calls_log from database
export interface ToolCallLogEntry {
  tool: string
  args: Record<string, unknown>
  result: string
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  code_suggestion?: string | null
  isStreaming?: boolean
  isInterrupted?: boolean  // True if AI was interrupted and can be continued
  interruptedRound?: number  // Round number when interrupted
  statusText?: string
  toolCalls?: ToolCallEntry[]
  toolCallsLog?: ToolCallLogEntry[]  // From API, for displaying full args
  saveSuggestion?: SaveSuggestion | null
  reasoningSnapshot?: string | null
}

export interface Conversation {
  id: number
  program_id: number | null
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
