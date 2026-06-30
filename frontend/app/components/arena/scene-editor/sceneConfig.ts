import { OFFICIAL_SCENE_CONFIG, OFFICIAL_SCENE_VERSION } from '../officialSceneConfig'
import { DEFAULT_NEWS_AREA, DEFAULT_WS_AREA, STORAGE_KEY } from './constants'
import type { NewsArea, SceneConfig, WorkstationArea } from './types'

export function getWsArea(config: SceneConfig | null): WorkstationArea {
  const ws = config?.workstationArea
  if (!ws) return DEFAULT_WS_AREA
  return {
    x: ws.x ?? DEFAULT_WS_AREA.x,
    y: ws.y ?? DEFAULT_WS_AREA.y,
    w: ws.w ?? DEFAULT_WS_AREA.w,
    h: ws.h ?? DEFAULT_WS_AREA.h,
    scale: ws.scale && !isNaN(ws.scale) ? ws.scale : DEFAULT_WS_AREA.scale,
  }
}

export function getNewsArea(config: SceneConfig | null): NewsArea {
  const na = config?.newsArea
  if (!na) return DEFAULT_NEWS_AREA
  return {
    x: na.x ?? DEFAULT_NEWS_AREA.x,
    y: na.y ?? DEFAULT_NEWS_AREA.y,
    w: na.w ?? DEFAULT_NEWS_AREA.w,
    h: na.h ?? DEFAULT_NEWS_AREA.h,
    scale: na.scale && !isNaN(na.scale) ? na.scale : DEFAULT_NEWS_AREA.scale,
  }
}

export function normalizeSceneConfig(config: Partial<SceneConfig> | null | undefined): SceneConfig {
  const officialConfig = OFFICIAL_SCENE_CONFIG
  const input = config || {}
  const sceneVersion = typeof input.sceneVersion === 'number'
    ? input.sceneVersion
    : typeof officialConfig.sceneVersion === 'number'
      ? officialConfig.sceneVersion
      : OFFICIAL_SCENE_VERSION

  return {
    sceneVersion,
    assets: Array.isArray(input.assets) ? input.assets : officialConfig.assets,
    animationMap: {
      ...officialConfig.animationMap,
      ...(input.animationMap || {}),
    },
    workstationArea: getWsArea(input as SceneConfig),
    newsArea: getNewsArea(input as SceneConfig),
  }
}

export function shouldUseOfficialConfig(config: Partial<SceneConfig> | null | undefined): boolean {
  if (!config) return true
  const localVersion = typeof config.sceneVersion === 'number' ? config.sceneVersion : 0
  const officialVersion = typeof OFFICIAL_SCENE_CONFIG.sceneVersion === 'number'
    ? OFFICIAL_SCENE_CONFIG.sceneVersion
    : OFFICIAL_SCENE_VERSION
  return localVersion < officialVersion
}

export function loadConfig(): SceneConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (!shouldUseOfficialConfig(parsed)) {
        return normalizeSceneConfig(parsed)
      }
    }
  } catch { /* ignore */ }
  return normalizeSceneConfig(OFFICIAL_SCENE_CONFIG)
}
