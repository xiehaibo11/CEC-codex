import type { MoodOption } from './types'

export const CHAR_SCALE = 1.6
export const CHAR_RENDER_SIZE = 64 * CHAR_SCALE
export const SCREEN_H = 260
export const SCREEN_GAP = 20
export const SCREEN_Y = 8
export const SCREEN_BORDER = 6
export const MOVE_SPEED = 0.4
export const ZONE_PAD = 4
export const CHAR_ZONE_DEPTH = 180
export const REPEL_DIST = 70

const EMOJI_PATH = '/static/arena-sprites/assets/emoji'

export const NEWS_MOOD: MoodOption = { img: `${EMOJI_PATH}/zap.png`, bg: '#4a1d96' }
export const FLOW_MOOD: MoodOption = { img: `${EMOJI_PATH}/star.png`, bg: '#1e3a5f' }
export const IDLE_MOODS: MoodOption[] = [
  { emoji: '☕', bg: '#3b2f1e' },
  { img: `${EMOJI_PATH}/grinning.png`, bg: '#14532d' },
]

export const SSE_BASE = '/api/market-intelligence/stream'
export const WATCHLIST_API = '/api/hyperliquid/symbols/watchlist'
