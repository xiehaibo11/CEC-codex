import {
  CHAR_RENDER_SIZE,
  FLOW_MOOD,
  IDLE_MOODS,
  MOVE_SPEED,
  NEWS_MOOD,
  REPEL_DIST,
} from './constants'
import type { CharacterBounds, IdleCharacter, WatchType } from './types'

function distance(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(v, max))
}

export function createInitialCharacters(availablePresets: number[], bounds: CharacterBounds): IdleCharacter[] {
  const placed: { x: number; y: number }[] = []
  return availablePresets.map((pid) => {
    let x = 0
    let y = 0
    for (let attempt = 0; attempt < 20; attempt++) {
      x = bounds.left + Math.random() * Math.max(0, bounds.right - bounds.left)
      y = bounds.top + Math.random() * Math.max(0, bounds.bottom - bounds.top)
      if (!placed.some((p) => distance(p, { x, y }) < REPEL_DIST)) break
    }
    placed.push({ x, y })
    return {
      presetId: pid, x, y, targetX: x, targetY: y,
      direction: Math.random() > 0.5 ? 'up' : 'up',
      state: Math.random() > 0.5 ? 'idle' : 'offline',
      mood: null, moodTimer: 0, behavior: 'idle',
    }
  })
}

export function advanceCharacters(
  prev: IdleCharacter[],
  dt: number,
  bounds: CharacterBounds,
): IdleCharacter[] {
  return prev.map((c, idx) => {
    if (c.behavior === 'idle') {
      if (c.mood && c.moodTimer > 0) {
        const mt = c.moodTimer - dt
        if (mt <= 0) return { ...c, mood: null, moodTimer: 0 }
        return { ...c, moodTimer: mt }
      }
      return c
    }
    const u = { ...c }
    if (u.mood && u.moodTimer > 0) {
      u.moodTimer -= dt
      if (u.moodTimer <= 0) { u.mood = null; u.moodTimer = 0 }
    }
    const dx = u.targetX - u.x
    const dy = u.targetY - u.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist > 2) {
      const blocked = prev.some((o, j) => j !== idx &&
        distance(o, u) < REPEL_DIST * 0.7 &&
        ((u.targetX - u.x) * (o.x - u.x) + (u.targetY - u.y) * (o.y - u.y)) > 0)
      if (blocked) {
        u.behavior = 'idle'
        u.state = Math.random() > 0.5 ? 'idle' : 'offline'
        u.direction = 'up'
        if (!u.mood) {
          u.mood = IDLE_MOODS[Math.floor(Math.random() * IDLE_MOODS.length)]
          u.moodTimer = 3000
        }
      } else {
        const step = MOVE_SPEED * (dt / 16)
        const ratio = Math.min(step / dist, 1)
        u.x += dx * ratio
        u.y += dy * ratio
        u.state = 'just_traded'
        u.direction = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : 'up'
      }
    } else if (u.behavior === 'walking' || u.behavior === 'watching') {
      u.behavior = 'idle'
      u.state = Math.random() > 0.5 ? 'idle' : 'offline'
      u.direction = 'up'
    }
    u.x = clamp(u.x, bounds.left, bounds.right)
    u.y = clamp(u.y, bounds.top, bounds.bottom)
    return u
  })
}

export function assignWatchTargets(
  prev: IdleCharacter[],
  type: WatchType,
  innerW: number,
  screenW: number,
  bounds: CharacterBounds,
): IdleCharacter[] {
  const idle = prev.filter((c) => c.behavior === 'idle')
  const count = Math.min(idle.length, 2 + Math.floor(Math.random() * 2))
  const chosenList = idle.sort(() => Math.random() - 0.5).slice(0, count)
  const chosenIds = new Set(chosenList.map((c) => c.presetId))
  const screenCx = innerW / 2
  const isNews = type === 'news'
  const moodOpt = isNews ? NEWS_MOOD : FLOW_MOOD
  const baseCx = isNews ? screenCx - screenW / 2 : screenCx + screenW / 2
  const spacing = CHAR_RENDER_SIZE + 10
  const occupied: { x: number; y: number }[] = prev
    .filter((c) => !chosenIds.has(c.presetId))
    .map((c) => ({ x: c.x, y: c.y }))
  const assigned: ({ x: number; y: number } | null)[] = []
  const totalSpread = (chosenList.length - 1) * spacing
  const startX = baseCx - totalSpread / 2
  for (let i = 0; i < chosenList.length; i++) {
    let sx = clamp(startX + i * spacing, bounds.left, bounds.right)
    let sy = bounds.top + (i % 2) * 20
    let clear = false
    for (let attempt = 0; attempt < 8; attempt++) {
      const tooClose = occupied.some((o) => distance(o, { x: sx, y: sy }) < REPEL_DIST * 0.7)
      if (!tooClose) { clear = true; break }
      sx += (attempt % 2 === 0 ? 1 : -1) * spacing * 0.5
      sy += 15
      sx = clamp(sx, bounds.left, bounds.right)
      sy = clamp(sy, bounds.top, bounds.bottom)
    }
    if (clear) {
      occupied.push({ x: sx, y: sy })
      assigned.push({ x: sx, y: sy })
    } else {
      assigned.push(null)
    }
  }
  let slotIdx = 0
  return prev.map((c) => {
    if (!chosenIds.has(c.presetId)) return c
    const slot = assigned[slotIdx++]
    if (!slot) {
      return { ...c, mood: moodOpt, moodTimer: 4000 + Math.random() * 2000 }
    }
    return {
      ...c, behavior: 'watching',
      targetX: slot.x, targetY: slot.y,
      mood: moodOpt, moodTimer: 4000 + Math.random() * 2000,
    }
  })
}
