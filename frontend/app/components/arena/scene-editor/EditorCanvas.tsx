import { useCallback, useEffect, useRef } from 'react'

import { CANVAS_H, CANVAS_W, WALL_H } from './constants'
import { getNewsArea, getWsArea } from './sceneConfig'
import type { NewsArea, PlacedAsset, SceneConfig, WorkstationArea } from './types'

type DragMode =
  | { type: 'move'; id: string; startX: number; startY: number; ox: number; oy: number }
  | { type: 'resize'; id: string; startX: number; startY: number; oScale: number; baseW: number; baseH: number }
  | { type: 'ws-move'; startX: number; startY: number; ox: number; oy: number }
  | { type: 'ws-resize'; startX: number; startY: number; ow: number; oh: number }
  | { type: 'news-move'; startX: number; startY: number; ox: number; oy: number }
  | { type: 'news-resize'; startX: number; startY: number; ow: number; oh: number }

export default function EditorCanvas({ config, selectedId, onSelect, onUpdate, onRemove, onUpdateWsArea, onUpdateNewsArea }: {
  config: SceneConfig; selectedId: string | null
  onSelect: (id: string | null) => void
  onUpdate: (id: string, patch: Partial<PlacedAsset>) => void
  onRemove: () => void
  onUpdateWsArea: (patch: Partial<WorkstationArea>) => void
  onUpdateNewsArea: (patch: Partial<NewsArea>) => void
}) {
  const dragRef = useRef<DragMode | null>(null)
  const selectedAsset = config.assets.find(a => a.id === selectedId)

  const onAssetDown = useCallback((e: React.MouseEvent, asset: PlacedAsset) => {
    e.stopPropagation()
    onSelect(asset.id)
    dragRef.current = {
      type: 'move', id: asset.id,
      startX: e.clientX, startY: e.clientY,
      ox: asset.x, oy: asset.y,
    }
  }, [onSelect])

  const onResizeDown = useCallback((e: React.MouseEvent, asset: PlacedAsset) => {
    e.stopPropagation()
    dragRef.current = {
      type: 'resize', id: asset.id,
      startX: e.clientX, startY: e.clientY,
      oScale: asset.scale,
      baseW: asset.cropW, baseH: asset.cropH,
    }
  }, [])

  const ws = getWsArea(config)
  const na = getNewsArea(config)

  const onWsDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    onSelect(null)
    dragRef.current = { type: 'ws-move', startX: e.clientX, startY: e.clientY, ox: ws.x, oy: ws.y }
  }, [ws, onSelect])

  const onWsResizeDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    dragRef.current = { type: 'ws-resize', startX: e.clientX, startY: e.clientY, ow: ws.w, oh: ws.h }
  }, [ws])

  const onNewsDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    onSelect(null)
    dragRef.current = { type: 'news-move', startX: e.clientX, startY: e.clientY, ox: na.x, oy: na.y }
  }, [na, onSelect])

  const onNewsResizeDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    dragRef.current = { type: 'news-resize', startX: e.clientX, startY: e.clientY, ow: na.w, oh: na.h }
  }, [na])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const d = dragRef.current
    if (!d) return
    if (d.type === 'move') {
      onUpdate(d.id, {
        x: Math.max(0, Math.min(CANVAS_W - 20, d.ox + e.clientX - d.startX)),
        y: Math.max(0, Math.min(CANVAS_H - 20, d.oy + e.clientY - d.startY)),
      })
    } else if (d.type === 'resize') {
      const dx = e.clientX - d.startX
      const dy = e.clientY - d.startY
      const diagonal = (dx + dy) / 2
      const origSize = Math.max(d.baseW, d.baseH) * d.oScale
      const newScale = Math.max(0.5, Math.min(8, d.oScale * (1 + diagonal / origSize)))
      onUpdate(d.id, { scale: Math.round(newScale * 10) / 10 })
    } else if (d.type === 'ws-move') {
      onUpdateWsArea({
        x: Math.max(0, Math.min(CANVAS_W - 100, d.ox + e.clientX - d.startX)),
        y: Math.max(0, Math.min(CANVAS_H - 100, d.oy + e.clientY - d.startY)),
      })
    } else if (d.type === 'ws-resize') {
      onUpdateWsArea({
        w: Math.max(200, Math.min(CANVAS_W, d.ow + e.clientX - d.startX)),
        h: Math.max(150, Math.min(CANVAS_H, d.oh + e.clientY - d.startY)),
      })
    } else if (d.type === 'news-move') {
      onUpdateNewsArea({
        x: Math.max(0, Math.min(CANVAS_W - 100, d.ox + e.clientX - d.startX)),
        y: Math.max(0, Math.min(CANVAS_H - 100, d.oy + e.clientY - d.startY)),
      })
    } else if (d.type === 'news-resize') {
      onUpdateNewsArea({
        w: Math.max(150, Math.min(CANVAS_W, d.ow + e.clientX - d.startX)),
        h: Math.max(120, Math.min(CANVAS_H, d.oh + e.clientY - d.startY)),
      })
    }
  }, [onUpdate, onUpdateWsArea])

  const onMouseUp = useCallback(() => { dragRef.current = null }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) onRemove()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selectedId, onRemove])

  return (
    <div style={{ flexShrink: 0 }}>
      {/* Toolbar above canvas */}
      <div className="flex items-center gap-2 mb-1 h-7">
        {selectedAsset ? (<>
          <span className="text-[11px] text-white/70 font-mono">{selectedAsset.label}</span>
          <span className="text-[11px] text-muted-foreground">
            {selectedAsset.cropW}×{selectedAsset.cropH}px
          </span>
          <div className="flex items-center gap-1 ml-2">
            <button onClick={() => onUpdate(selectedAsset.id, { scale: Math.max(0.5, selectedAsset.scale - 0.5) })}
              className="px-2 py-0.5 text-xs bg-black/60 rounded text-white hover:bg-black/80 border border-border/30">−</button>
            <span className="px-2 py-0.5 text-xs text-white/70 bg-black/40 rounded min-w-[32px] text-center">
              {selectedAsset.scale}x
            </span>
            <button onClick={() => onUpdate(selectedAsset.id, { scale: Math.min(8, selectedAsset.scale + 0.5) })}
              className="px-2 py-0.5 text-xs bg-black/60 rounded text-white hover:bg-black/80 border border-border/30">+</button>
          </div>
          <button onClick={onRemove}
            className="px-2 py-0.5 text-xs bg-red-900/60 rounded text-red-300 hover:bg-red-900/80 border border-red-800/30 ml-2">
            删除
          </button>
          <span className="text-[10px] text-muted-foreground/50 ml-2">
            pos: ({Math.round(selectedAsset.x)}, {Math.round(selectedAsset.y)})
          </span>
        </>) : (
          <span className="text-[11px] text-muted-foreground">点击素材选中，拖动移位，角标拖动缩放</span>
        )}
      </div>
      {/* Canvas */}
      <div className="relative border border-border/30 rounded-lg cursor-crosshair"
        style={{ width: CANVAS_W, height: CANVAS_H, overflow: 'hidden' }}
        onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}
        onClick={() => onSelect(null)}>
        {/* Wall */}
        <div className="absolute inset-x-0 top-0" style={{ height: WALL_H }}>
          <div className="absolute inset-0" style={{
            background: 'linear-gradient(180deg, #d4cfc8 0%, #c8c2b8 60%, #b8b0a4 100%)',
          }} />
          <div className="absolute inset-0" style={{
            opacity: 0.06,
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.1) 3px, rgba(0,0,0,0.1) 4px)',
          }} />
          <div className="absolute bottom-0 left-0 right-0" style={{
            height: 7,
            background: 'linear-gradient(180deg, #8a7e6e 0%, #6e6456 100%)',
            borderTop: '1px solid #9e9282',
          }} />
        </div>
        {/* Floor */}
        <div className="absolute inset-x-0 bottom-0" style={{ top: WALL_H }}>
          <div className="absolute inset-0" style={{
            background: 'linear-gradient(180deg, #c4a87a 0%, #b89a6e 30%, #a88e64 100%)',
          }} />
          <div className="absolute inset-0" style={{
            opacity: 0.08,
            backgroundImage: `repeating-linear-gradient(90deg, transparent, transparent 79px, rgba(0,0,0,0.15) 79px, rgba(0,0,0,0.15) 80px),
              repeating-linear-gradient(0deg, transparent, transparent 15px, rgba(0,0,0,0.05) 15px, rgba(0,0,0,0.05) 16px)`,
          }} />
          <div className="absolute top-0 left-0 right-0" style={{
            height: 12,
            background: 'linear-gradient(180deg, rgba(0,0,0,0.08), transparent)',
          }} />
        </div>
        {/* Placed assets */}
        {config.assets.map(a => {
          const isSelected = selectedId === a.id
          const dispW = a.cropW * a.scale
          const dispH = a.cropH * a.scale
          return (
            <div key={a.id} className="absolute" style={{
              left: a.x, top: a.y, zIndex: isSelected ? 50 : 10,
            }}
              onMouseDown={e => onAssetDown(e, a)}
              onClick={e => e.stopPropagation()}>
              {a.src === '__widget_clock__' ? (
                <div style={{
                  outline: isSelected ? '2px solid #3b82f6' : 'none',
                  outlineOffset: 1, cursor: 'move',
                }}>
                  <div style={{
                    fontFamily: 'monospace', fontSize: 11 * a.scale, fontWeight: 'bold',
                    color: '#8b9cf7', textShadow: '0 0 6px rgba(139,156,247,0.4)',
                    background: 'linear-gradient(180deg, #1a1a2e, #16162a)',
                    border: '2px solid #2a2a4a', borderRadius: 3,
                    padding: `${2 * a.scale}px ${8 * a.scale}px`,
                    whiteSpace: 'nowrap', lineHeight: 1.2,
                  }}>00:00:00</div>
                </div>
              ) : (
                <div style={{
                  width: dispW, height: dispH,
                  overflow: 'hidden',
                  outline: isSelected ? '2px solid #3b82f6' : 'none',
                  outlineOffset: 1,
                  cursor: 'move',
                }}>
                  <div style={{
                    width: a.cropW, height: a.cropH,
                    backgroundImage: `url(${a.src})`,
                    backgroundSize: 'auto',
                    backgroundPosition: `-${a.cropX}px -${a.cropY}px`,
                    backgroundRepeat: 'no-repeat',
                    imageRendering: 'pixelated',
                    transform: `scale(${a.scale})`,
                    transformOrigin: 'top left',
                  }} />
                </div>
              )}
              {/* Resize handle (bottom-right corner) */}
              {isSelected && (
                <div
                  onMouseDown={e => onResizeDown(e, a)}
                  style={{
                    position: 'absolute',
                    right: -4, bottom: -4,
                    width: 10, height: 10,
                    background: '#3b82f6',
                    border: '1px solid #fff',
                    borderRadius: 2,
                    cursor: 'nwse-resize',
                    zIndex: 60,
                  }}
                />
              )}
            </div>
          )
        })}
        {/* Workstation area placeholder */}
        {(() => {
          const refW1 = Math.round(250 * ws.scale)
          const refW2 = Math.round(440 * ws.scale)
          const refH = Math.round(260 * ws.scale)
          return (
            <div className="absolute" style={{
              left: ws.x, top: ws.y, width: ws.w, height: ws.h,
              border: '2px dashed rgba(139,156,247,0.5)',
              borderRadius: 6,
              background: 'rgba(139,156,247,0.05)',
              cursor: 'move',
              zIndex: 5,
              overflow: 'hidden',
            }}
              onMouseDown={onWsDown}
              onClick={e => e.stopPropagation()}>
              {/* Header info */}
              <div className="absolute top-1 left-2 right-20 text-[10px] font-mono"
                style={{ color: 'rgba(139,156,247,0.7)', zIndex: 2 }}>
                Workstation Zone · {ws.scale}x · 1-mon: {refW1}×{refH} · 2-mon: {refW2}×{refH}
              </div>
              {/* Reference grid: repeating workstation-sized cells */}
              <div className="absolute inset-0 pointer-events-none" style={{
                top: 16,
                backgroundImage: `
                  repeating-linear-gradient(90deg,
                    rgba(139,156,247,0.15) 0px, rgba(139,156,247,0.15) 1px,
                    transparent 1px, transparent ${refW1}px),
                  repeating-linear-gradient(0deg,
                    rgba(139,156,247,0.15) 0px, rgba(139,156,247,0.15) 1px,
                    transparent 1px, transparent ${refH}px)
                `,
                backgroundSize: `${refW1}px ${refH}px`,
              }} />
              {/* Scale controls */}
              <div className="absolute bottom-1 left-2 flex items-center gap-1" style={{ zIndex: 2 }}
                onClick={e => e.stopPropagation()}
                onMouseDown={e => e.stopPropagation()}>
                <button onClick={() => onUpdateWsArea({ scale: Math.max(0.3, Math.round((ws.scale - 0.05) * 100) / 100) })}
                  className="px-1.5 py-0 text-[10px] rounded" style={{ background: 'rgba(139,156,247,0.3)', color: '#c8d0ff' }}>−</button>
                <span className="text-[10px] font-mono" style={{ color: 'rgba(139,156,247,0.7)' }}>{ws.scale}x</span>
                <button onClick={() => onUpdateWsArea({ scale: Math.min(2, Math.round((ws.scale + 0.05) * 100) / 100) })}
                  className="px-1.5 py-0 text-[10px] rounded" style={{ background: 'rgba(139,156,247,0.3)', color: '#c8d0ff' }}>+</button>
              </div>
              {/* Resize handle */}
              <div onMouseDown={onWsResizeDown} style={{
                position: 'absolute', right: -5, bottom: -5,
                width: 10, height: 10,
                background: '#8b9cf7', border: '1px solid #fff',
                borderRadius: 2, cursor: 'nwse-resize', zIndex: 60,
              }} />
            </div>
          )
        })()}
        {/* News area placeholder */}
        <div className="absolute" style={{
          left: na.x, top: na.y, width: na.w, height: na.h,
          border: '2px dashed rgba(74,222,128,0.5)',
          borderRadius: 6,
          background: 'rgba(74,222,128,0.05)',
          cursor: 'move',
          zIndex: 5,
          overflow: 'hidden',
        }}
          onMouseDown={onNewsDown}
          onClick={e => e.stopPropagation()}>
          <div className="absolute top-1 left-2 right-20 text-[10px] font-mono"
            style={{ color: 'rgba(74,222,128,0.7)', zIndex: 2 }}>
            News Zone · {na.scale}x
          </div>
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center"
            style={{ top: 16 }}>
            <div className="text-[10px] font-mono text-center"
              style={{ color: 'rgba(74,222,128,0.3)' }}>
              空闲角色 + 屏幕
            </div>
          </div>
          <div className="absolute bottom-1 left-2 flex items-center gap-1" style={{ zIndex: 2 }}
            onClick={e => e.stopPropagation()}
            onMouseDown={e => e.stopPropagation()}>
            <button onClick={() => onUpdateNewsArea({ scale: Math.max(0.3, Math.round((na.scale - 0.05) * 100) / 100) })}
              className="px-1.5 py-0 text-[10px] rounded" style={{ background: 'rgba(74,222,128,0.3)', color: '#a7f3d0' }}>−</button>
            <span className="text-[10px] font-mono" style={{ color: 'rgba(74,222,128,0.7)' }}>{na.scale}x</span>
            <button onClick={() => onUpdateNewsArea({ scale: Math.min(2, Math.round((na.scale + 0.05) * 100) / 100) })}
              className="px-1.5 py-0 text-[10px] rounded" style={{ background: 'rgba(74,222,128,0.3)', color: '#a7f3d0' }}>+</button>
          </div>
          <div onMouseDown={onNewsResizeDown} style={{
            position: 'absolute', right: -5, bottom: -5,
            width: 10, height: 10,
            background: '#4ade80', border: '1px solid #fff',
            borderRadius: 2, cursor: 'nwse-resize', zIndex: 60,
          }} />
        </div>
        {/* Grid overlay */}
        <div className="absolute inset-0 pointer-events-none" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }} />
      </div>
    </div>
  )
}
