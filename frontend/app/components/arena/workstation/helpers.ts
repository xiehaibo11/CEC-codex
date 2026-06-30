import type { CharacterState, MoodOption } from './types'

export const EXCHANGE_LABEL: Record<string, { short: string; color: string }> = {
  hyperliquid: { short: 'HL', color: '#6ee7b7' },
  binance: { short: 'BN', color: '#f0b90b' },
}

export const MOVE_DURATION_MS = 1100
export const ACTIVITY_DWELL_MS = 7000

export function getScreenBg(pnl: number | null): string {
  if (pnl && pnl > 0) return '#071208'
  if (pnl && pnl < 0) return '#120708'
  return '#070a12'
}

const EMOJI_PATH = '/static/arena-sprites/assets/emoji'

export const STATE_MOODS: Partial<Record<CharacterState, MoodOption[]>> = {
  offline: [{ img: `${EMOJI_PATH}/sleeping.png`, bg: '#1e293b' }],
  idle: [
    { emoji: '☕', bg: '#3b2f1e' },
    { img: `${EMOJI_PATH}/lightbulb.png`, bg: '#1e3a5f' },
  ],
  holding_profit: [{ img: `${EMOJI_PATH}/grinning.png`, bg: '#14532d' }],
  holding_loss: [{ img: `${EMOJI_PATH}/sad.png`, bg: '#78350f' }],
  just_traded: [{ img: `${EMOJI_PATH}/zap.png`, bg: '#4a1d96' }],
  ai_thinking: [{ img: `${EMOJI_PATH}/robot.png`, bg: '#1e3a5f' }],
  error: [{ img: `${EMOJI_PATH}/angry.png`, bg: '#7f1d1d' }],
}
