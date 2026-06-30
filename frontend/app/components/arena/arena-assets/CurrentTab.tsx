import PixelCharacter from '../PixelCharacter'
import AnimatedSprite from './AnimatedSprite'
import {
  DIRECTIONS,
  DIR_OFFSETS,
  FULL_ANIMS,
  MAPPED_ANIMS,
  STATES,
} from './constants'
import PresetSelector from './PresetSelector'
import type { PresetSelectorProps } from './types'

export default function CurrentTab({ preset, onPresetChange }: PresetSelectorProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-semibold mb-2">Select Preset</h2>
        <PresetSelector preset={preset} onPresetChange={onPresetChange} />
      </div>

      <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-3">
        <p className="text-xs text-muted-foreground">
          Updated state→animation mappings using the <b>full LPC sheet</b>. Each state now has a distinct animation.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="border-collapse">
          <thead>
            <tr>
              <th className="p-2 text-xs text-left">State</th>
              {DIRECTIONS.map(d => (
                <th key={d} className="p-2 text-xs text-center">{d}</th>
              ))}
              <th className="p-2 text-xs text-left">Animation Used</th>
            </tr>
          </thead>
          <tbody>
            {STATES.map(state => (
              <tr key={state} className="border-t border-border/30">
                <td className="p-2 text-xs font-mono whitespace-nowrap">{state}</td>
                {DIRECTIONS.map(dir => (
                  <td key={dir} className="p-2">
                    <div className="bg-black/30 rounded flex items-center justify-center"
                      style={{ width: 80, height: 80 }}>
                      <PixelCharacter presetId={preset} state={state}
                        direction={dir} scale={1.2} />
                    </div>
                  </td>
                ))}
                <td className="p-2 text-xs text-emerald-400 font-mono">
                  {{ offline: 'sit (frame 0)',
                     idle: 'idle (2f)',
                     holding_profit: 'slash (6f)',
                     holding_loss: 'combat_idle (2f)',
                     program_running: 'spellcast (7f)',
                     ai_thinking: 'combat_idle (2f)',
                     just_traded: 'jump/run',
                     error: 'hurt/emote',
                  }[state] || 'idle'}
                </td>
              </tr>
            ))}
            <tr><td colSpan={6} className="pt-4 pb-2 text-xs font-semibold text-amber-400">
              Unmapped Animations (available)
            </td></tr>
            {FULL_ANIMS.filter(a => !MAPPED_ANIMS.has(a.name)).map(anim => (
              <tr key={anim.name} className="border-t border-amber-500/20">
                <td className="p-2 text-xs font-mono whitespace-nowrap text-amber-300">{anim.name}</td>
                {DIRECTIONS.map((dir, di) => (
                  <td key={dir} className="p-2">
                    <div className="bg-black/30 rounded flex items-center justify-center"
                      style={{ width: 80, height: 80 }}>
                      {anim.dirs === 1 && di > 0 ? (
                        <span className="text-[9px] text-muted-foreground/30">N/A</span>
                      ) : (
                        <AnimatedSprite presetId={preset}
                          baseRow={anim.baseRow}
                          dirOffset={anim.dirs === 1 ? 0 : DIR_OFFSETS[dir]}
                          frames={anim.frames} speed={200} />
                      )}
                    </div>
                  </td>
                ))}
                <td className="p-2 text-xs text-amber-400 font-mono">
                  {anim.use}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-blue-500/10 border border-blue-500/30 rounded p-3">
        <h3 className="text-sm font-semibold text-blue-400">State → Animation Mapping</h3>
        <div className="grid grid-cols-2 gap-1 mt-2 text-xs text-muted-foreground">
          <span>offline → sit frame 0 (seated)</span>
          <span>idle → idle (subtle breathing)</span>
          <span>holding_profit → slash (arm swing celebrate)</span>
          <span>holding_loss → combat_idle (tense stance)</span>
          <span>program_running → spellcast (typing motion)</span>
          <span>ai_thinking → combat_idle (focused)</span>
          <span>just_traded → jump (up/down) / run (left/right)</span>
          <span>error → hurt (south) / emote (other dirs)</span>
        </div>
      </div>
    </div>
  )
}
