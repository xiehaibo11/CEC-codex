export interface Conversation {
  id: number
  title: string
  message_count: number
  is_bot_conversation?: boolean
  updated_at: string
}

export interface BotConfig {
  platform: string
  bot_username: string | null
  status: string
}

export interface DiscordBotConfig extends BotConfig {
  bot_app_id?: string
}

export interface ToolCallEntry {
  type: 'tool_call' | 'tool_result' | 'reasoning' | 'subagent_progress' | 'confirmation_required' | 'tool_error'
  name?: string
  tool?: string
  args?: Record<string, unknown>
  result?: string
  content?: string
  subagent?: string
  step?: string
  round?: number
  max_rounds?: number
  taskId?: string
  confirmationId?: string
  description?: string
  status?: 'pending' | 'confirmed' | 'cancelled' | 'failed'
  message?: string
  severity?: string
}

// API format for tool_calls_log from database
export interface ToolCallLogEntry {
  tool: string
  args: Record<string, unknown>
  result: string
}

/**
 * Represents a successfully created entity that should be displayed as a card.
 * Extracted from tool_calls_log when save_xxx tools return success: true.
 */
export interface CreatedEntityCard {
  type: 'prompt' | 'program' | 'signal_pool' | 'ai_trader' | 'factor'
  id: number
  name: string
  content?: string
  viewUrl: string
}

export interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  reasoning_snapshot?: string
  tool_calls_log?: string
  is_complete?: boolean
  interrupt_reason?: string
  created_at?: string
  // Streaming state
  isStreaming?: boolean
  statusText?: string
  toolCalls?: ToolCallEntry[]
  isInterrupted?: boolean
  interruptedRound?: number
}

export interface CompressionPoint {
  message_id: number
  summary: string
  compressed_at: string
}

export interface SkillInfo {
  name: string
  description: string
  description_zh: string
  command: string
  enabled: boolean
}

export interface TokenUsage {
  current_tokens: number
  max_tokens: number
  usage_ratio: number
  show_warning: boolean
}

export interface LLMProvider {
  id: string
  name: string
  models: string[]
  base_url?: string
}
