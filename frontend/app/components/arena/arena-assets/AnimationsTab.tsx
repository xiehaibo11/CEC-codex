import { DIR_LABELS, FULL_ANIMS } from './constants'
import PresetSelector from './PresetSelector'
import SpriteFrame from './SpriteFrame'
import type { PresetSelectorProps } from './types'

export default function AnimationsTab({ preset, onPresetChange }: PresetSelectorProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-semibold mb-2">Select Preset</h2>
        <PresetSelector preset={preset} onPresetChange={onPresetChange} />
      </div>

      <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-3">
        <p className="text-xs text-muted-foreground">
          All 15 animations from the <b>full LPC sheet</b> (54 rows). Switch preset above to see different characters.
        </p>
      </div>

      <div className="space-y-4">
        {FULL_ANIMS.map(anim => (
          <div key={anim.name}
            className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3">
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-sm font-bold font-mono">{anim.name}</span>
                <span className="text-xs text-muted-foreground ml-2">
                  {anim.frames}f × {anim.dirs} dir{anim.dirs > 1 ? 's' : ''}
                  {' '}| rows {anim.baseRow}-{anim.baseRow + anim.dirs - 1}
                </span>
                <span className="text-xs text-muted-foreground ml-2">— {anim.desc}</span>
              </div>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">
                {anim.use}
              </span>
            </div>
            <div className="bg-black/30 rounded p-2 overflow-x-auto">
              {Array.from({ length: anim.dirs }).map((_, d) => (
                <div key={d} className="flex items-center gap-0.5 mb-0.5">
                  <span className="text-[9px] text-muted-foreground/40 font-mono w-16 shrink-0">
                    {DIR_LABELS[d] || `Dir ${d}`}
                  </span>
                  {Array.from({ length: anim.frames }).map((_, f) => (
                    <SpriteFrame key={f} presetId={preset}
                      row={anim.baseRow + d} col={f} scale={1} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
