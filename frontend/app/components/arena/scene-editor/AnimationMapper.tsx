import { useEffect, useState } from 'react'

import { ANIM_LOOKUP, ANIM_OPTIONS, STATE_LABELS } from './constants'

function AnimPreview({ animName }: { animName: string }) {
  const anim = ANIM_LOOKUP[animName]
  const [col, setCol] = useState(0)
  const scale = 0.8
  const size = 64 * scale
  const sheetW = 13 * size
  const sheetH = 54 * size
  // Show south-facing (dirOffset 2 for 4-dir, 0 for 1-dir)
  const row = anim ? anim.baseRow + (anim.dirs > 1 ? 2 : 0) : 0
  const frames = anim?.frames || 1

  useEffect(() => {
    if (frames <= 1) { setCol(0); return }
    let idx = 0
    const t = setInterval(() => { idx = (idx + 1) % frames; setCol(idx) }, 200)
    return () => clearInterval(t)
  }, [animName, frames])

  if (!anim) return null
  return (
    <div style={{
      width: size, height: size, flexShrink: 0,
      backgroundImage: 'url(/static/arena-sprites/avatar_01.png)',
      backgroundSize: `${sheetW}px ${sheetH}px`,
      backgroundPosition: `-${col * size}px -${row * size}px`,
      imageRendering: 'pixelated',
    }} />
  )
}

export default function AnimationMapper({ map, onChange }: {
  map: Record<string, string>; onChange: (state: string, anim: string) => void
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">动画映射（全局）</h3>
      <div className="grid grid-cols-2 gap-2" style={{ maxWidth: 800 }}>
        {Object.entries(STATE_LABELS).map(([state, label]) => (
          <div key={state} className="flex items-center gap-2 bg-black/20 rounded px-3 py-1.5">
            <AnimPreview animName={map[state] || 'idle'} />
            <span className="text-xs font-mono w-36 shrink-0">{label}</span>
            <select value={map[state] || 'idle'} onChange={e => onChange(state, e.target.value)}
              className="flex-1 text-xs bg-black/40 border border-border/30 rounded px-2 py-1 text-white">
              {ANIM_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  )
}
