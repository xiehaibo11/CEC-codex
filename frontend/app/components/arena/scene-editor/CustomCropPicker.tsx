import { ALL_FILES } from './constants'

export default function CustomCropPicker({ onSelect, onCancel }: {
  onSelect: (src: string) => void; onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center" onClick={onCancel}>
      <div className="bg-[#1a1c28] rounded-lg border border-border/50 p-4 max-w-lg" onClick={e => e.stopPropagation()}>
        <div className="text-sm font-semibold mb-3">选择精灵图进行裁切</div>
        <div className="grid grid-cols-2 gap-1 max-h-[60vh] overflow-y-auto">
          {ALL_FILES.map(f => (
            <button key={`${f.cat}/${f.file}`}
              onClick={() => onSelect(`/static/arena-sprites/assets/${f.cat}/${f.file}`)}
              className="text-left px-2 py-1.5 text-[11px] rounded hover:bg-white/10 text-muted-foreground hover:text-white">
              <span className="text-white/40">{f.cat}/</span>{f.file}
            </button>
          ))}
        </div>
        <button onClick={onCancel} className="mt-3 px-3 py-1 text-xs bg-muted rounded">取消</button>
      </div>
    </div>
  )
}
