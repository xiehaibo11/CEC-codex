import type { PresetSelectorProps } from './types'

export default function PresetSelector({ preset, onPresetChange }: PresetSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {Array.from({ length: 12 }, (_, i) => i + 1).map(id => (
        <button key={id} onClick={() => onPresetChange(id)}
          className={`w-10 h-10 rounded border text-xs font-mono ${
            preset === id ? 'border-primary bg-primary/20' : 'border-border'
          }`}
          style={{
            backgroundImage: `url(/static/arena-sprites/avatar_${String(id).padStart(2, '0')}.png)`,
            backgroundSize: '130px 160px',
            backgroundPosition: '0 -40px',
            imageRendering: 'pixelated',
          }}
        />
      ))}
    </div>
  )
}
