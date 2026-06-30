import type { AssetItem, NewsArea, WorkstationArea } from './types'

export const STORAGE_KEY = 'arena_scene_config'
export const CANVAS_W = 900
export const CANVAS_H = 560
export const WALL_H = 80

export const DEFAULT_WS_AREA: WorkstationArea = { x: 16, y: 86, w: 868, h: 460, scale: 1 }
export const DEFAULT_NEWS_AREA: NewsArea = { x: 540, y: 100, w: 340, h: 420, scale: 0.5 }

export const ANIM_OPTIONS = [
  { value: 'spellcast', label: 'Spellcast (7f)', baseRow: 0, frames: 7, dirs: 4 },
  { value: 'thrust', label: 'Thrust (8f)', baseRow: 4, frames: 8, dirs: 4 },
  { value: 'walk', label: 'Walk (9f)', baseRow: 8, frames: 9, dirs: 4 },
  { value: 'slash', label: 'Slash (6f)', baseRow: 12, frames: 6, dirs: 4 },
  { value: 'shoot', label: 'Shoot (13f)', baseRow: 16, frames: 13, dirs: 4 },
  { value: 'hurt', label: 'Hurt (6f, south only)', baseRow: 20, frames: 6, dirs: 1 },
  { value: 'climb', label: 'Climb (6f, north only)', baseRow: 21, frames: 6, dirs: 1 },
  { value: 'idle', label: 'Idle (2f)', baseRow: 22, frames: 2, dirs: 4 },
  { value: 'jump', label: 'Jump (5f)', baseRow: 26, frames: 5, dirs: 4 },
  { value: 'sit', label: 'Sit (3f)', baseRow: 30, frames: 3, dirs: 4 },
  { value: 'emote', label: 'Emote (3f)', baseRow: 34, frames: 3, dirs: 4 },
  { value: 'run', label: 'Run (8f)', baseRow: 38, frames: 8, dirs: 4 },
  { value: 'combat_idle', label: 'Combat Idle (2f)', baseRow: 42, frames: 2, dirs: 4 },
  { value: 'backslash', label: 'Backslash (13f)', baseRow: 46, frames: 13, dirs: 4 },
  { value: 'halfslash', label: 'Halfslash (6f)', baseRow: 50, frames: 6, dirs: 4 },
]

export const ANIM_LOOKUP = Object.fromEntries(ANIM_OPTIONS.map(a => [a.value, a]))

export const DEFAULT_ANIM_MAP: Record<string, string> = {
  idle: 'idle',
  holding_profit: 'slash',
  holding_loss: 'combat_idle',
  just_traded: 'jump',
  program_running: 'spellcast',
  ai_thinking: 'combat_idle',
  error: 'emote',
  offline: 'sit',
}

export const ITEMS_PATH = '/static/arena-sprites/assets/items'

// Catalog grouped by category for the palette
export const ITEM_CATALOG: Record<string, AssetItem[]> = {
  doors: [
    { id: 'door-wood-plain', label: 'Wood Plain Door', file: 'door-wood-plain.png', w: 64, h: 68 },
    { id: 'door-wood-panels', label: 'Wood Panels Door', file: 'door-wood-panels.png', w: 64, h: 68 },
    { id: 'door-iron-grid', label: 'Iron Grid Door', file: 'door-iron-grid.png', w: 64, h: 68 },
    { id: 'door-dark-wood', label: 'Dark Wood Door', file: 'door-dark-wood.png', w: 64, h: 68 },
    { id: 'door-brown-rustic', label: 'Brown Rustic Door', file: 'door-brown-rustic.png', w: 64, h: 68 },
    { id: 'door-iron-dark', label: 'Iron Dark Door', file: 'door-iron-dark.png', w: 64, h: 68 },
    { id: 'door-double', label: 'Double Door', file: 'door-double.png', w: 64, h: 96 },
    { id: 'door-double-win', label: 'Double Door Window', file: 'door-double-win.png', w: 64, h: 96 },
  ],
  office: [
    { id: 'laptop-0-0', label: 'Laptop Dark Open', file: 'laptop-0-0.png', w: 32, h: 32 },
    { id: 'laptop-0-2', label: 'Laptop Light Open', file: 'laptop-0-2.png', w: 32, h: 32 },
    { id: 'laptop-1-0', label: 'Laptop Blue Open', file: 'laptop-1-0.png', w: 32, h: 32 },
    { id: 'tv-off', label: 'TV Off', file: 'tv-off.png', w: 96, h: 64 },
    { id: 'tv-color', label: 'TV Color Bars', file: 'tv-color.png', w: 96, h: 64 },
    { id: 'tv-static-1', label: 'TV Static', file: 'tv-static-1.png', w: 96, h: 64 },
    { id: 'coffee-cup', label: 'Coffee Cup', file: 'coffee-cup.png', w: 32, h: 32 },
    { id: 'coffee-maker-1', label: 'Coffee Maker', file: 'coffee-maker-1.png', w: 32, h: 32 },
    { id: 'copier', label: 'Copy Machine', file: 'copier.png', w: 64, h: 64 },
    { id: 'water-cooler-1', label: 'Water Cooler', file: 'water-cooler-1.png', w: 32, h: 64 },
    { id: 'water-cooler-3', label: 'Water Cooler 2', file: 'water-cooler-3.png', w: 32, h: 64 },
    { id: 'shopping-cart', label: 'Shopping Cart', file: 'shopping-cart.png', w: 32, h: 64 },
    { id: 'desk-top', label: 'Desk Top View', file: 'desk-top.png', w: 160, h: 64 },
    { id: 'desk-front', label: 'Desk Front View', file: 'desk-front.png', w: 160, h: 64 },
    { id: 'bin-0-0', label: 'Bin Green', file: 'bin-0-0.png', w: 32, h: 32 },
    { id: 'bin-0-1', label: 'Bin Dark', file: 'bin-0-1.png', w: 32, h: 32 },
    { id: 'bin-2-0', label: 'Bin Blue', file: 'bin-2-0.png', w: 32, h: 32 },
    { id: 'portrait-1', label: 'Portrait Gold', file: 'portrait-1.png', w: 32, h: 32 },
    { id: 'portrait-2', label: 'Portrait Brown', file: 'portrait-2.png', w: 32, h: 32 },
    { id: 'chair-black', label: 'Chair Black', file: 'chair-black.png', w: 18, h: 42 },
    { id: 'chair-red', label: 'Chair Red', file: 'chair-red.png', w: 18, h: 42 },
    { id: 'filing-cabinet-1', label: 'Filing Cabinet', file: 'filing-cabinet-1.png', w: 32, h: 64 },
    { id: 'cabinet-dark', label: 'Dark Cabinet', file: 'cabinet-dark.png', w: 64, h: 64 },
    { id: 'office-plant', label: 'Office Plant', file: 'office-plant.png', w: 32, h: 32 },
    { id: 'book-stack', label: 'Book Stack', file: 'book-stack.png', w: 32, h: 32 },
    { id: 'desk-lamp', label: 'Desk Lamp', file: 'desk-lamp.png', w: 32, h: 64 },
    { id: 'work-desk', label: 'Work Desk', file: 'work-desk.png', w: 64, h: 32 },
  ],
  furniture: [
    { id: 'bookshelf-brown-1', label: 'Bookshelf Brown', file: 'bookshelf-brown-1.png', w: 64, h: 96 },
    { id: 'bookshelf-green-1', label: 'Bookshelf Green', file: 'bookshelf-green-1.png', w: 64, h: 96 },
    { id: 'wardrobe-1', label: 'Wardrobe', file: 'wardrobe-1.png', w: 64, h: 80 },
    { id: 'display-case', label: 'Display Case', file: 'display-case.png', w: 64, h: 96 },
    { id: 'china-cabinet', label: 'China Cabinet', file: 'china-cabinet.png', w: 48, h: 96 },
    { id: 'curtain-gold', label: 'Gold Curtain', file: 'curtain-gold.png', w: 64, h: 80 },
    { id: 'lamp-table', label: 'Table Lamp', file: 'lamp-table.png', w: 32, h: 48 },
    { id: 'bed-single', label: 'Single Bed', file: 'bed-single.png', w: 64, h: 80 },
    { id: 'fireplace', label: 'Fireplace', file: 'fireplace.png', w: 64, h: 48 },
    { id: 'chair-wood-1', label: 'Wood Chair', file: 'chair-wood-1.png', w: 32, h: 32 },
    { id: 'chair-gold-1', label: 'Gold Chair', file: 'chair-gold-1.png', w: 32, h: 32 },
    { id: 'floor-lamp-1', label: 'Floor Lamp', file: 'floor-lamp-1.png', w: 32, h: 64 },
    { id: 'armchair-1', label: 'Armchair', file: 'armchair-1.png', w: 32, h: 32 },
    { id: 'sofa-front-1', label: 'Sofa Front', file: 'sofa-front-1.png', w: 64, h: 32 },
    { id: 'pillar-1', label: 'Pillar', file: 'pillar-1.png', w: 32, h: 64 },
  ],
  plants: [
    { id: 'tree-round', label: 'Round Tree', file: 'tree-round.png', w: 16, h: 32 },
    { id: 'tree-tall', label: 'Tall Tree', file: 'tree-tall.png', w: 16, h: 32 },
    { id: 'tulips', label: 'Tulips', file: 'tulips.png', w: 16, h: 16 },
    { id: 'fern-pot', label: 'Fern Pot', file: 'fern-pot.png', w: 16, h: 16 },
    { id: 'cactus', label: 'Cactus', file: 'cactus.png', w: 16, h: 16 },
    { id: 'flower-pot', label: 'Flower Pot', file: 'flower-pot.png', w: 16, h: 16 },
    { id: 'indoor-plant-1', label: 'Indoor Plant', file: 'indoor-plant-1.png', w: 16, h: 32 },
    { id: 'rug-red', label: 'Red Rug', file: 'rug-red.png', w: 48, h: 32 },
    { id: 'rug-blue', label: 'Blue Rug', file: 'rug-blue.png', w: 48, h: 32 },
    { id: 'barrel', label: 'Barrel', file: 'barrel.png', w: 32, h: 32 },
  ],
  screens: [
    { id: 'tv-modern-white', label: 'Modern TV', file: 'tv-modern-white.png', w: 180, h: 180 },
    { id: 'tv-modern-empty', label: 'TV Frame', file: 'tv-modern-empty.png', w: 180, h: 180 },
    { id: 'scifi-panel-tall', label: 'Sci-fi Panel', file: 'scifi-panel-tall.png', w: 32, h: 64 },
    { id: 'scifi-screen-1', label: 'Sci-fi Screen', file: 'scifi-screen-1.png', w: 32, h: 32 },
    { id: 'scifi-console-1', label: 'Sci-fi Console', file: 'scifi-console-1.png', w: 32, h: 32 },
  ],
  signs: [
    { id: 'sign-hyper-arena', label: 'CEC-codex', file: 'sign-hyper-arena.png', w: 124, h: 30 },
  ],
  widgets: [
    { id: 'widget-clock', label: 'Live Clock', file: '__widget_clock__', w: 80, h: 14 },
  ],
}

export const ALL_FILES: { cat: string; file: string }[] = [
  { cat: 'doors', file: 'animated-doors.png' }, { cat: 'doors', file: 'doors-v1.png' },
  { cat: 'doors', file: 'door-rework.png' }, { cat: 'doors', file: 'door-rework-windows.png' },
  { cat: 'office', file: 'Laptop.png' }, { cat: 'office', file: 'TV, Widescreen.png' },
  { cat: 'office', file: 'Desk, Ornate.png' }, { cat: 'office', file: 'Coffee Maker.png' },
  { cat: 'office', file: 'Water Cooler.png' }, { cat: 'office', file: 'Bins.png' },
  { cat: 'office', file: 'office-appliances.png' }, { cat: 'office', file: 'office-chairs.png' },
  { cat: 'furniture', file: 'shelves-brown.png' }, { cat: 'furniture', file: 'house-insides.png' },
  { cat: 'furniture', file: 'upholstery.png' }, { cat: 'furniture', file: 'wooden-dark.png' },
  { cat: 'plants', file: 'potted-plants.png' }, { cat: 'plants', file: 'lpc-plants.png' },
  { cat: 'plants', file: 'rpg-indoor-expansion.png' },
  { cat: 'screens', file: 'scifi-tiles.png' }, { cat: 'screens', file: 'computer-screen.png' },
]

export const STATE_LABELS: Record<string, string> = {
  idle: '空闲（无持仓）',
  holding_profit: '持仓盈利',
  holding_loss: '持仓亏损',
  just_traded: '刚刚交易',
  program_running: '程序运行中',
  ai_thinking: 'AI 思考中',
  error: '错误',
  offline: '离线',
}
