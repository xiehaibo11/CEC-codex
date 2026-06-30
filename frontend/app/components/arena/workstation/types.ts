import type { CharacterState } from '../pixelData/characters'
import type { ExchangeMonitor, MonitorPosition } from '../TradingFloor'

export type { CharacterState, ExchangeMonitor, MonitorPosition }

export interface WorkstationProps {
  traderName: string
  exchanges: ExchangeMonitor[]
  avatarPresetId: number | null
  state: CharacterState
  animationMap?: Record<string, string>
  activitySignal?: {
    seq: number
    exchange: string
    state: 'program_running' | 'ai_thinking'
  }
}

export type CharacterDirection = 'up' | 'down' | 'left' | 'right'

export type MoodOption = {
  bg: string
  img?: string
  emoji?: string
}
