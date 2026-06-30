import type { CharacterState } from '../pixelData/characters'
import type { CharacterDirection } from '../PixelCharacter'

export const STATES: CharacterState[] = [
  'idle', 'holding_profit', 'holding_loss', 'just_traded',
  'program_running', 'ai_thinking', 'error', 'offline',
]

export const DIRECTIONS: CharacterDirection[] = ['up', 'down', 'left', 'right']

export const MOODS = [
  { emoji: '😴', label: 'Sleep', bg: '#1e293b' },
  { emoji: '😄', label: 'Profit', bg: '#14532d' },
  { emoji: '😍', label: 'Big Profit', bg: '#064e3b' },
  { emoji: '🎉', label: 'Celebrate', bg: '#064e3b' },
  { emoji: '😡', label: 'Big Loss', bg: '#7f1d1d' },
  { emoji: '😥', label: 'Loss', bg: '#78350f' },
  { emoji: '😰', label: 'Anxiety', bg: '#78350f' },
  { emoji: '🤔', label: 'Thinking', bg: '#1e3a5f' },
  { emoji: '🤖', label: 'Robot', bg: '#1e3a5f' },
  { emoji: '💡', label: 'Idea', bg: '#1e3a5f' },
  { emoji: '⚡', label: 'Trading', bg: '#4a1d96' },
  { emoji: '☕', label: 'Break', bg: '#3b2f1e' },
  { emoji: '📰', label: 'News', bg: '#1e293b' },
]

// All 15 animations from full LPC sheet (54 rows, baseRow = first row in sheet)
export const FULL_ANIMS = [
  { name: 'spellcast', baseRow: 0, frames: 7, dirs: 4, desc: 'Arms raised & moving',
    use: 'Typing / Working' },
  { name: 'thrust', baseRow: 4, frames: 8, dirs: 4, desc: 'Stabbing/pierce motion',
    use: 'Pointing at screen' },
  { name: 'walk', baseRow: 8, frames: 9, dirs: 4, desc: 'Standard walk cycle',
    use: 'Walking between workstations' },
  { name: 'slash', baseRow: 12, frames: 6, dirs: 4, desc: 'Arm swing motion',
    use: 'Celebration / Excitement' },
  { name: 'shoot', baseRow: 16, frames: 13, dirs: 4, desc: 'Ranged attack pose',
    use: 'Available for future use' },
  { name: 'hurt', baseRow: 20, frames: 6, dirs: 1, desc: 'Crouching down in pain',
    use: 'Big loss reaction (south only)' },
  { name: 'climb', baseRow: 21, frames: 6, dirs: 1, desc: 'Ladder climbing',
    use: 'Available for future use' },
  { name: 'idle', baseRow: 22, frames: 2, dirs: 4, desc: 'Subtle breathing',
    use: 'Default standing state' },
  { name: 'jump', baseRow: 26, frames: 5, dirs: 4, desc: 'Jumping up',
    use: 'Big profit celebration' },
  { name: 'sit', baseRow: 30, frames: 3, dirs: 4, desc: 'Stand-to-seated',
    use: 'Offline / Sleeping' },
  { name: 'emote', baseRow: 34, frames: 3, dirs: 4, desc: 'Expressive gestures',
    use: 'Reaction to events' },
  { name: 'run', baseRow: 38, frames: 8, dirs: 4, desc: 'Fast movement',
    use: 'Rushing to trade / Urgent' },
  { name: 'combat_idle', baseRow: 42, frames: 2, dirs: 4, desc: 'Alert fist stance',
    use: 'Focused / AI thinking' },
  { name: 'backslash', baseRow: 46, frames: 13, dirs: 4, desc: 'Two-handed overhead swing',
    use: 'Strong action / Available' },
  { name: 'halfslash', baseRow: 50, frames: 6, dirs: 4, desc: 'Short one-hand slash',
    use: 'Quick action / Available' },
]

export const DIR_LABELS = ['North (back)', 'West', 'South (front)', 'East']

export const DIR_OFFSETS: Record<string, number> = { up: 0, down: 2, left: 1, right: 3 }

export const MAPPED_ANIMS = new Set([
  'spellcast', 'slash', 'hurt', 'idle', 'jump', 'sit', 'emote', 'run', 'combat_idle',
])

export const SCENE_ASSETS: Record<string, { file: string; label: string }[]> = {
  doors: [
    { file: 'animated-doors.png', label: 'Animated Doors (wood+iron, open/close)' },
    { file: 'doors-v1.png', label: 'Windows & Doors v1 (many styles)' },
    { file: 'door-rework.png', label: 'Door Rework (plain)' },
    { file: 'door-rework-windows.png', label: 'Door Rework (with windows)' },
  ],
  office: [
    { file: 'Laptop.png', label: 'Laptop (on/off)' },
    { file: 'TV, Widescreen.png', label: 'Widescreen TV' },
    { file: 'Desk, Ornate.png', label: 'Ornate Desk' },
    { file: 'Copy Machine.png', label: 'Copy Machine' },
    { file: 'Coffee Maker.png', label: 'Coffee Maker' },
    { file: 'Coffee Cup.png', label: 'Coffee Cup' },
    { file: 'Water Cooler.png', label: 'Water Cooler' },
    { file: 'Bins.png', label: 'Waste Bins' },
    { file: 'Office Portraits.png', label: 'Portraits' },
    { file: 'Rotary Phones.png', label: 'Phones' },
    { file: 'office-appliances.png', label: 'Office Appliances (CC0)' },
    { file: 'office-chairs.png', label: 'Office Chairs' },
  ],
  furniture: [
    { file: 'wooden-dark.png', label: 'Dark Wood Furniture' },
    { file: 'wooden-blonde.png', label: 'Blonde Wood Furniture' },
    { file: 'upholstery.png', label: 'Sofas/Chairs/Lamps' },
    { file: 'shelves-brown.png', label: 'Bookshelf Brown' },
    { file: 'shelves-green.png', label: 'Bookshelf Green' },
    { file: 'house-insides.png', label: 'House Insides' },
    { file: 'house-interior.png', label: 'House Interior Pack' },
  ],
  plants: [
    { file: 'potted-plants.png', label: 'Potted Plants' },
    { file: 'flowers-cc0.png', label: 'Flowers (CC0)' },
    { file: 'rpg-indoor-expansion.png', label: 'RPG Indoor (plants+rugs)' },
    { file: 'lpc-plants.png', label: 'LPC Plants & Fungi' },
  ],
  screens: [
    { file: 'tv-modern-white.png', label: 'Modern TV (white)' },
    { file: 'tv-modern-empty.png', label: 'Modern TV (empty, CC0)' },
    { file: 'tv-retro.gif', label: 'Retro TV (animated)' },
    { file: 'computer-screen.png', label: 'CRT Monitor' },
    { file: 'scifi-tiles.png', label: 'Sci-fi Tiles (CC0)' },
  ],
}
