export interface ModelChatEntry {
  id: number
  account_id: number
  account_name: string
  operation: string
  symbol: string | null
  reason: string
  executed: boolean
  decision_time: string | null
  realized_pnl?: number | null
  has_snapshot?: boolean
  prompt_snapshot?: string
  reasoning_snapshot?: string
  decision_snapshot?: string
}

export interface PromptBacktestProps {
  accountId: string
  tradingMode?: string
  exchange?: string
}

export interface SelectedRecord extends ModelChatEntry {
  modifiedPrompt: string
  // Search/replace state
  isMatched?: boolean        // Whether keyword was found
  isSelected?: boolean       // Whether selected for replacement (default true)
  isModified?: boolean       // Whether already replaced
  matchContext?: string      // Matched line with context
}
