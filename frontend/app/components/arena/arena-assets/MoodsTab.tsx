import { MOODS } from './constants'

export default function MoodsTab() {
  return (
    <div className="space-y-6">
      <h2 className="text-sm font-semibold">Mood Bubbles</h2>
      <p className="text-xs text-muted-foreground">
        Showcase of the bubble styles used by the live Arena view, including robot and idle variants.
      </p>
      <div className="flex flex-wrap gap-4">
        {MOODS.map(m => (
          <div key={m.label} className="flex flex-col items-center gap-2">
            <div className="relative">
              <div style={{
                position: 'relative',
                background: m.bg, border: '2px solid rgba(255,255,255,0.2)',
                borderRadius: 10, padding: '3px 6px', fontSize: 15, lineHeight: 1,
                boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
              }}>
                {m.emoji}
                <div style={{
                  position: 'absolute', bottom: -6, left: 3,
                  width: 0, height: 0,
                  borderTop: `6px solid ${m.bg}`,
                  borderRight: '6px solid transparent',
                }} />
              </div>
            </div>
            <span className="text-xs text-muted-foreground">{m.label}</span>
          </div>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2">Size Variants</h3>
        <div className="flex gap-6 items-end">
          {[12, 15, 18, 22].map(size => (
            <div key={size} className="flex flex-col items-center gap-1">
              <div style={{
                position: 'relative',
                background: '#14532d', border: '2px solid rgba(255,255,255,0.2)',
                borderRadius: 10, padding: '3px 6px', fontSize: size, lineHeight: 1,
                boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
              }}>
                😄
                <div style={{
                  position: 'absolute', bottom: -6, left: 3,
                  width: 0, height: 0,
                  borderTop: '6px solid #14532d',
                  borderRight: '6px solid transparent',
                }} />
              </div>
              <span className="text-xs text-muted-foreground">{size}px</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-blue-500/10 border border-blue-500/30 rounded p-3">
        <h3 className="text-sm font-semibold text-blue-400">Current State → Bubble Mapping</h3>
        <div className="grid grid-cols-2 gap-1 mt-2 text-xs text-muted-foreground">
          <span>offline → 😴</span><span>idle → ☕ or 💡</span>
          <span>holding_profit → 😄 or 😍</span><span>holding_loss → 😥 or 😰</span>
          <span>just_traded → ⚡</span><span>program_running → movement only</span>
          <span>ai_thinking → 🤖</span><span>error → 😡</span>
          <span>big_profit → 🎉</span><span>watching_news → 📰</span>
          <span>coffee_break → ☕</span>
        </div>
      </div>
    </div>
  )
}
