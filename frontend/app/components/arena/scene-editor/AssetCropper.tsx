import { useRef, useState } from 'react'

export default function AssetCropper({ src, label, onConfirm, onCancel }: {
  src: string; label: string
  onConfirm: (cx: number, cy: number, cw: number, ch: number) => void
  onCancel: () => void
}) {
  const [sel, setSel] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [drawing, setDrawing] = useState(false)
  const [start, setStart] = useState({ x: 0, y: 0 })
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 })
  const imgRef = useRef<HTMLImageElement>(null)
  const zoom = 2

  const onImgLoad = () => {
    if (imgRef.current) {
      setImgSize({ w: imgRef.current.naturalWidth, h: imgRef.current.naturalHeight })
    }
  }

  const getPos = (e: React.MouseEvent) => {
    const rect = imgRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return {
      x: Math.round(((e.clientX - rect.left) / rect.width) * imgSize.w),
      y: Math.round(((e.clientY - rect.top) / rect.height) * imgSize.h),
    }
  }

  const onDown = (e: React.MouseEvent) => {
    const p = getPos(e)
    setStart(p)
    setSel({ x: p.x, y: p.y, w: 1, h: 1 })
    setDrawing(true)
  }

  const onMove = (e: React.MouseEvent) => {
    if (!drawing) return
    const p = getPos(e)
    const x = Math.min(start.x, p.x)
    const y = Math.min(start.y, p.y)
    setSel({ x, y, w: Math.abs(p.x - start.x), h: Math.abs(p.y - start.y) })
  }

  const onUp = () => setDrawing(false)

  const dispW = imgSize.w * zoom
  const dispH = imgSize.h * zoom

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center"
      onClick={onCancel}>
      <div className="bg-[#1a1c28] rounded-lg border border-border/50 p-4 max-w-[90vw] max-h-[90vh] flex flex-col gap-3"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">裁切：{label}</span>
          <span className="text-xs text-muted-foreground">
            {sel ? `${sel.w}×${sel.h}px 起点(${sel.x},${sel.y})` : '点击并拖动以选择区域'}
          </span>
        </div>
        <div className="overflow-auto" style={{ maxHeight: '70vh' }}>
          <div className="relative" style={{ width: dispW || 'auto', height: dispH || 'auto', cursor: 'crosshair' }}
            onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
            <img ref={imgRef} src={src} alt={label} onLoad={onImgLoad}
              draggable={false} style={{
                imageRendering: 'pixelated',
                width: dispW || 'auto', height: dispH || 'auto',
              }} />
            {sel && sel.w > 0 && sel.h > 0 && (
              <div className="absolute border-2 border-blue-400 bg-blue-400/10 pointer-events-none" style={{
                left: sel.x * zoom, top: sel.y * zoom,
                width: sel.w * zoom, height: sel.h * zoom,
              }} />
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {sel && sel.w > 2 && sel.h > 2 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">预览：</span>
              <div className="border border-border/30 bg-black/40 p-1" style={{
                width: sel.w * 2 + 8, height: sel.h * 2 + 8,
              }}>
                <div style={{
                  width: sel.w * 2, height: sel.h * 2,
                  backgroundImage: `url(${src})`,
                  backgroundPosition: `-${sel.x * 2}px -${sel.y * 2}px`,
                  backgroundSize: `${imgSize.w * 2}px ${imgSize.h * 2}px`,
                  imageRendering: 'pixelated',
                }} />
              </div>
            </div>
          )}
          <div className="flex gap-2 ml-auto">
            <button onClick={onCancel}
              className="px-3 py-1.5 rounded text-xs bg-muted hover:bg-muted/80">取消</button>
            <button disabled={!sel || sel.w < 2 || sel.h < 2}
              onClick={() => sel && onConfirm(sel.x, sel.y, sel.w, sel.h)}
              className="px-3 py-1.5 rounded text-xs bg-primary text-primary-foreground disabled:opacity-30">
              放置到画布
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
