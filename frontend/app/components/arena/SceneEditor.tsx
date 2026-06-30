import { useCallback, useEffect, useState } from 'react'

import { OFFICIAL_SCENE_VERSION } from './officialSceneConfig'
import AnimationMapper from './scene-editor/AnimationMapper'
import AssetCropper from './scene-editor/AssetCropper'
import AssetPalette from './scene-editor/AssetPalette'
import {
  CANVAS_H,
  CANVAS_W,
  DEFAULT_ANIM_MAP,
  DEFAULT_NEWS_AREA,
  DEFAULT_WS_AREA,
  ITEMS_PATH,
  STORAGE_KEY,
} from './scene-editor/constants'
import CustomCropPicker from './scene-editor/CustomCropPicker'
import EditorCanvas from './scene-editor/EditorCanvas'
import { loadConfig, normalizeSceneConfig, shouldUseOfficialConfig } from './scene-editor/sceneConfig'
import type { AssetItem, NewsArea, PlacedAsset, SceneConfig, WorkstationArea } from './scene-editor/types'

// Re-export the public contract so existing importers keep working unchanged.
export type { NewsArea, PlacedAsset, SceneConfig, WorkstationArea } from './scene-editor/types'
export { CANVAS_H, CANVAS_W, DEFAULT_NEWS_AREA, DEFAULT_WS_AREA, STORAGE_KEY } from './scene-editor/constants'
export {
  getNewsArea,
  getWsArea,
  normalizeSceneConfig,
  shouldUseOfficialConfig,
} from './scene-editor/sceneConfig'

export default function SceneEditor() {
  const [config, setConfig] = useState<SceneConfig>(loadConfig)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [cropSrc, setCropSrc] = useState<string | null>(null)
  const [customCropOpen, setCustomCropOpen] = useState(false)
  const [saved, setSaved] = useState(false)

  const save = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }, [config])

  const placeItem = useCallback((item: AssetItem) => {
    const isWidget = item.file.startsWith('__widget_')
    const defaultScale = isWidget ? 1 : Math.max(2, Math.min(4, Math.round(64 / Math.max(item.w, item.h) * 3)))
    const asset: PlacedAsset = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      src: isWidget ? item.file : `${ITEMS_PATH}/${item.file}`,
      label: item.label,
      x: CANVAS_W / 2 - (item.w * defaultScale) / 2,
      y: CANVAS_H / 2 - (item.h * defaultScale) / 2,
      scale: defaultScale, cropX: 0, cropY: 0, cropW: item.w, cropH: item.h,
    }
    setConfig(c => ({ ...c, assets: [...c.assets, asset] }))
  }, [])

  const addAsset = useCallback((src: string, label: string,
    cropX: number, cropY: number, cropW: number, cropH: number) => {
    const asset: PlacedAsset = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      src, label, x: CANVAS_W / 2 - (cropW * 2) / 2, y: CANVAS_H / 2 - (cropH * 2) / 2,
      scale: 2, cropX, cropY, cropW, cropH,
    }
    setConfig(c => ({ ...c, assets: [...c.assets, asset] }))
    setCropSrc(null)
  }, [])

  const removeSelected = useCallback(() => {
    if (!selectedId) return
    setConfig(c => ({ ...c, assets: c.assets.filter(a => a.id !== selectedId) }))
    setSelectedId(null)
  }, [selectedId])

  const updateAsset = useCallback((id: string, patch: Partial<PlacedAsset>) => {
    setConfig(c => ({
      ...c,
      assets: c.assets.map(a => a.id === id ? { ...a, ...patch } : a),
    }))
  }, [])

  const setAnim = useCallback((state: string, anim: string) => {
    setConfig(c => ({
      ...c, animationMap: { ...c.animationMap, [state]: anim },
    }))
  }, [])

  const updateWsArea = useCallback((patch: Partial<WorkstationArea>) => {
    setConfig(c => ({
      ...c,
      workstationArea: { ...(c.workstationArea || DEFAULT_WS_AREA), ...patch },
    }))
  }, [])

  const updateNewsArea = useCallback((patch: Partial<NewsArea>) => {
    setConfig(c => ({
      ...c,
      newsArea: { ...(c.newsArea || DEFAULT_NEWS_AREA), ...patch },
    }))
  }, [])

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const parsed = raw ? JSON.parse(raw) : null
      if (shouldUseOfficialConfig(parsed)) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(loadConfig()))
      }
    } catch {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(loadConfig()))
    }
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <button onClick={save}
          className="px-3 py-1.5 rounded text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-500">
          {saved ? '已保存！' : '保存配置'}
        </button>
        <button onClick={() => setConfig(normalizeSceneConfig({
          sceneVersion: config.sceneVersion ?? OFFICIAL_SCENE_VERSION,
          assets: [],
          animationMap: { ...DEFAULT_ANIM_MAP },
          workstationArea: { ...DEFAULT_WS_AREA },
          newsArea: { ...DEFAULT_NEWS_AREA },
        }))}
          className="px-3 py-1.5 rounded text-sm font-medium bg-red-900/50 text-red-300 hover:bg-red-900/70">
          重置全部
        </button>
        <span className="text-xs text-muted-foreground ml-2">
          已放置 {config.assets.length} 个素材
        </span>
      </div>

      <div className="flex gap-4" style={{ minHeight: CANVAS_H + 40 }}>
        <AssetPalette onPlace={placeItem} onCustomCrop={() => setCustomCropOpen(true)} />
        <EditorCanvas config={config} selectedId={selectedId}
          onSelect={setSelectedId} onUpdate={updateAsset} onRemove={removeSelected}
          onUpdateWsArea={updateWsArea} onUpdateNewsArea={updateNewsArea} />
      </div>

      {customCropOpen && !cropSrc && (
        <CustomCropPicker onSelect={src => setCropSrc(src)} onCancel={() => setCustomCropOpen(false)} />
      )}
      {cropSrc && (
        <AssetCropper src={cropSrc} label={cropSrc.split('/').pop() || 'asset'}
          onConfirm={(cX, cY, cW, cH) => { addAsset(cropSrc, cropSrc.split('/').pop() || 'asset', cX, cY, cW, cH); setCustomCropOpen(false) }}
          onCancel={() => { setCropSrc(null); setCustomCropOpen(false) }}
        />
      )}

      <AnimationMapper map={config.animationMap} onChange={setAnim} />
    </div>
  )
}
