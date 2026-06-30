import { useState } from 'react'

import { CANVAS_H, ITEM_CATALOG, ITEMS_PATH } from './constants'
import type { AssetItem } from './types'

export default function AssetPalette({ onPlace, onCustomCrop }: {
  onPlace: (item: AssetItem) => void
  onCustomCrop: () => void
}) {
  const [openCat, setOpenCat] = useState<string | null>('office')
  return (
    <div className="w-52 shrink-0 overflow-y-auto border border-border/30 rounded-lg bg-black/20"
      style={{ maxHeight: CANVAS_H + 68 }}>
      <div className="p-2 text-xs font-semibold border-b border-border/30 flex justify-between">
        <span>素材</span>
        <button onClick={onCustomCrop}
          className="text-[10px] text-blue-400 hover:text-blue-300">自定义裁切</button>
      </div>
      {Object.entries(ITEM_CATALOG).map(([cat, items]) => (
        <div key={cat}>
          <button onClick={() => setOpenCat(openCat === cat ? null : cat)}
            className="w-full text-left px-2 py-1.5 text-xs font-medium capitalize hover:bg-white/5 flex justify-between">
            {cat} <span className="text-muted-foreground text-[10px]">{items.length}</span>
          </button>
          {openCat === cat && (
            <div className="px-1 pb-2 flex flex-wrap gap-1">
              {items.map(item => (
                <button key={item.id} onClick={() => onPlace(item)}
                  className="relative group rounded border border-transparent hover:border-blue-500/50 bg-black/30 hover:bg-black/50 p-1"
                  title={item.label}>
                  {item.file.startsWith('__widget_') ? (
                    <div className="flex items-center justify-center" style={{ width: 48, height: 32 }}>
                      <span className="text-[9px] font-mono text-blue-400">{item.label}</span>
                    </div>
                  ) : (
                    <img src={`${ITEMS_PATH}/${item.file}`} alt={item.label}
                      draggable={false}
                      style={{
                        maxWidth: 48, maxHeight: 48,
                        imageRendering: 'pixelated',
                      }} />
                  )}
                  <div className="absolute inset-x-0 bottom-0 text-[8px] text-white/70 bg-black/60 text-center leading-tight opacity-0 group-hover:opacity-100 truncate px-0.5">
                    {item.label}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
