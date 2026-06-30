import type { CharacterDirection } from '../PixelCharacter'
import type { CharacterState } from '../pixelData/characters'

export interface SSENewsItem {
  id: number
  title: string
  ai_summary?: string | null
  published_at?: string | null
  symbols?: string[]
  sentiment?: string | null
}

export interface SSEFlowSummary {
  symbol: string
  net_inflow: number
  buy_ratio: number
  large_order_net: number
  large_buy_count: number
  large_sell_count: number
  open_interest_change_pct?: number | null
  funding_rate_pct?: number | null
  latest_trade_timestamp?: number | null
}

export type MoodOption = { bg: string; img?: string; emoji?: string }

export interface IdleCharacter {
  presetId: number
  x: number
  y: number
  targetX: number
  targetY: number
  direction: CharacterDirection
  state: CharacterState
  mood: MoodOption | null
  moodTimer: number
  behavior: 'idle' | 'walking' | 'watching'
}

export interface NewsZoneProps {
  areaW: number
  areaH: number
  scale: number
  boundTraderPresetIds: Set<number>
  animationMap?: Record<string, string>
}

export interface CharacterBounds {
  left: number
  right: number
  top: number
  bottom: number
}

export type WatchType = 'news' | 'flow'
